/**
 * Production Monitoring Dashboard
 * ================================
 * Real-time monitoring of system health, risk metrics, rate limits, and execution statistics.
 * Integrates with new production-ready backend utilities.
 * 
 * Created: January 12, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  LinearProgress,
  Chip,
  Alert,
  IconButton,
  Tooltip,
  CircularProgress,
  Divider,
  Card,
  CardContent,
  Collapse,
  Button
} from '@mui/material';
import {
  MonitorHeart as HealthIcon,
  Speed as RateLimitIcon,
  Shield as RiskIcon,
  TrendingUp as ExecutionIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  CheckCircle as OkIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon
} from '@mui/icons-material';

const API_BASE = '/api/production';
const REFRESH_INTERVAL = 5000; // 5 seconds

// Status color mapping
const getStatusColor = (status) => {
  switch (status?.toLowerCase()) {
    case 'healthy':
    case 'low':
    case 'ok':
      return 'success';
    case 'degraded':
    case 'medium':
    case 'warning':
      return 'warning';
    case 'critical':
    case 'high':
    case 'error':
      return 'error';
    default:
      return 'default';
  }
};

const getStatusIcon = (status) => {
  switch (status?.toLowerCase()) {
    case 'healthy':
    case 'low':
    case 'ok':
      return <OkIcon sx={{ color: 'success.main' }} />;
    case 'degraded':
    case 'medium':
    case 'warning':
      return <WarningIcon sx={{ color: 'warning.main' }} />;
    case 'critical':
    case 'high':
    case 'error':
      return <ErrorIcon sx={{ color: 'error.main' }} />;
    default:
      return <InfoIcon sx={{ color: 'info.main' }} />;
  }
};

// Health Panel Component
function HealthPanel({ data, loading }) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (!data) {
    return (
      <Alert severity="info">Health monitor not available</Alert>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        {getStatusIcon(data.overall_status)}
        <Typography variant="subtitle1">
          Status: <strong>{data.overall_status?.toUpperCase()}</strong>
        </Typography>
      </Box>
      
      <Grid container spacing={2}>
        <Grid item xs={4}>
          <Typography variant="caption" color="text.secondary">CPU</Typography>
          <LinearProgress 
            variant="determinate" 
            value={data.cpu_percent || 0} 
            color={data.cpu_percent > 80 ? 'error' : data.cpu_percent > 60 ? 'warning' : 'success'}
            sx={{ height: 8, borderRadius: 1 }}
          />
          <Typography variant="body2">{data.cpu_percent?.toFixed(1)}%</Typography>
        </Grid>
        
        <Grid item xs={4}>
          <Typography variant="caption" color="text.secondary">Memory</Typography>
          <LinearProgress 
            variant="determinate" 
            value={data.memory_percent || 0}
            color={data.memory_percent > 85 ? 'error' : data.memory_percent > 70 ? 'warning' : 'success'}
            sx={{ height: 8, borderRadius: 1 }}
          />
          <Typography variant="body2">{data.memory_percent?.toFixed(1)}%</Typography>
        </Grid>
        
        <Grid item xs={4}>
          <Typography variant="caption" color="text.secondary">Disk</Typography>
          <LinearProgress 
            variant="determinate" 
            value={data.disk_percent || 0}
            color={data.disk_percent > 90 ? 'error' : data.disk_percent > 80 ? 'warning' : 'success'}
            sx={{ height: 8, borderRadius: 1 }}
          />
          <Typography variant="body2">{data.disk_percent?.toFixed(1)}%</Typography>
        </Grid>
      </Grid>
    </Box>
  );
}

// Rate Limits Panel Component
function RateLimitsPanel({ data, loading }) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (!data) {
    return (
      <Alert severity="info">Rate limiters not available</Alert>
    );
  }

  return (
    <Grid container spacing={2}>
      {Object.entries(data).map(([name, limit]) => (
        <Grid item xs={4} key={name}>
          <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'capitalize' }}>
            {name} API
          </Typography>
          <LinearProgress 
            variant="determinate" 
            value={limit.usage_percent || 0}
            color={limit.usage_percent > 80 ? 'error' : limit.usage_percent > 50 ? 'warning' : 'success'}
            sx={{ height: 8, borderRadius: 1 }}
          />
          <Typography variant="body2">
            {limit.remaining}/{limit.max} remaining
          </Typography>
        </Grid>
      ))}
    </Grid>
  );
}

// Risk Panel Component
function RiskPanel({ data, loading }) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (!data) {
    return (
      <Alert severity="info">Risk manager not available</Alert>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        {getStatusIcon(data.risk_level)}
        <Typography variant="subtitle1">
          Risk Level: <strong>{data.risk_level?.toUpperCase()}</strong>
        </Typography>
        <Chip 
          label={data.can_trade !== false ? 'Trading Allowed' : 'Trading Blocked'} 
          color={data.can_trade !== false ? 'success' : 'error'}
          size="small"
        />
      </Box>
      
      <Grid container spacing={2}>
        {data.volatility_regime && (
          <Grid item xs={6}>
            <Typography variant="caption" color="text.secondary">Volatility Regime</Typography>
            <Typography variant="body2">{data.volatility_regime}</Typography>
          </Grid>
        )}
        {data.drawdown !== undefined && (
          <Grid item xs={6}>
            <Typography variant="caption" color="text.secondary">Max Drawdown</Typography>
            <Typography variant="body2" color={data.drawdown > 15 ? 'error.main' : 'text.primary'}>
              {data.drawdown?.toFixed(2)}%
            </Typography>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}

// Execution Stats Panel Component
function ExecutionPanel({ data, loading }) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (!data) {
    return (
      <Alert severity="info">Execution statistics not available</Alert>
    );
  }

  return (
    <Grid container spacing={2}>
      <Grid item xs={3}>
        <Typography variant="caption" color="text.secondary">Orders Placed</Typography>
        <Typography variant="h6">{data.orders_placed || 0}</Typography>
      </Grid>
      <Grid item xs={3}>
        <Typography variant="caption" color="text.secondary">Orders Filled</Typography>
        <Typography variant="h6" color="success.main">{data.orders_filled || 0}</Typography>
      </Grid>
      <Grid item xs={3}>
        <Typography variant="caption" color="text.secondary">Orders Failed</Typography>
        <Typography variant="h6" color="error.main">{data.orders_failed || 0}</Typography>
      </Grid>
      <Grid item xs={3}>
        <Typography variant="caption" color="text.secondary">Fill Rate</Typography>
        <Typography variant="h6">{data.fill_rate?.toFixed(1) || 0}%</Typography>
      </Grid>
      
      {data.rate_limit_waits > 0 && (
        <Grid item xs={12}>
          <Alert severity="info" sx={{ py: 0.5 }}>
            Rate limit waits: {data.rate_limit_waits} (API throttling prevented)
          </Alert>
        </Grid>
      )}
      
      {data.validation_failures > 0 && (
        <Grid item xs={12}>
          <Alert severity="warning" sx={{ py: 0.5 }}>
            Validation failures: {data.validation_failures} (orders blocked before submission)
          </Alert>
        </Grid>
      )}
    </Grid>
  );
}

// Main Production Monitoring Dashboard
export default function ProductionMonitoringDashboard() {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [expanded, setExpanded] = useState({
    health: true,
    rateLimits: true,
    risk: true,
    execution: true
  });

  const fetchDashboardData = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/dashboard`);
      const data = await response.json();
      
      if (data.status === 'success') {
        setDashboardData(data.dashboard);
        setLastUpdate(new Date().toLocaleTimeString());
        setError(null);
      } else {
        setError(data.error || 'Failed to fetch dashboard data');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  const toggleSection = (section) => {
    setExpanded(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const handleRefresh = () => {
    setLoading(true);
    fetchDashboardData();
  };

  if (error) {
    return (
      <Alert severity="error" action={
        <Button color="inherit" size="small" onClick={handleRefresh}>
          Retry
        </Button>
      }>
        {error}
      </Alert>
    );
  }

  return (
    <Paper sx={{ p: 2 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">
          🔒 Production Monitoring
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {lastUpdate && (
            <Typography variant="caption" color="text.secondary">
              Updated: {lastUpdate}
            </Typography>
          )}
          <Tooltip title="Refresh">
            <IconButton size="small" onClick={handleRefresh} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Grid container spacing={2}>
        {/* System Health */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent sx={{ pb: 1 }}>
              <Box 
                sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
                onClick={() => toggleSection('health')}
              >
                <HealthIcon sx={{ mr: 1, color: 'primary.main' }} />
                <Typography variant="subtitle2" sx={{ flexGrow: 1 }}>System Health</Typography>
                {expanded.health ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </Box>
              <Collapse in={expanded.health}>
                <Box sx={{ mt: 1 }}>
                  <HealthPanel data={dashboardData?.health} loading={loading} />
                </Box>
              </Collapse>
            </CardContent>
          </Card>
        </Grid>

        {/* Rate Limits */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent sx={{ pb: 1 }}>
              <Box 
                sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
                onClick={() => toggleSection('rateLimits')}
              >
                <RateLimitIcon sx={{ mr: 1, color: 'info.main' }} />
                <Typography variant="subtitle2" sx={{ flexGrow: 1 }}>API Rate Limits</Typography>
                {expanded.rateLimits ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </Box>
              <Collapse in={expanded.rateLimits}>
                <Box sx={{ mt: 1 }}>
                  <RateLimitsPanel data={dashboardData?.rate_limits} loading={loading} />
                </Box>
              </Collapse>
            </CardContent>
          </Card>
        </Grid>

        {/* Risk Metrics */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent sx={{ pb: 1 }}>
              <Box 
                sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
                onClick={() => toggleSection('risk')}
              >
                <RiskIcon sx={{ mr: 1, color: 'warning.main' }} />
                <Typography variant="subtitle2" sx={{ flexGrow: 1 }}>Risk Status</Typography>
                {expanded.risk ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </Box>
              <Collapse in={expanded.risk}>
                <Box sx={{ mt: 1 }}>
                  <RiskPanel data={dashboardData?.risk} loading={loading} />
                </Box>
              </Collapse>
            </CardContent>
          </Card>
        </Grid>

        {/* Execution Statistics */}
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent sx={{ pb: 1 }}>
              <Box 
                sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
                onClick={() => toggleSection('execution')}
              >
                <ExecutionIcon sx={{ mr: 1, color: 'success.main' }} />
                <Typography variant="subtitle2" sx={{ flexGrow: 1 }}>Execution Stats</Typography>
                {expanded.execution ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </Box>
              <Collapse in={expanded.execution}>
                <Box sx={{ mt: 1 }}>
                  <ExecutionPanel data={dashboardData?.execution} loading={loading} />
                </Box>
              </Collapse>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Paper>
  );
}
