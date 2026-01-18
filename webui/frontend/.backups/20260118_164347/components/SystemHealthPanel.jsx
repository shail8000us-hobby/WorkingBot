import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  LinearProgress,
  Alert,
  AlertTitle,
  Chip,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tooltip
} from '@mui/material';
import {
  Activity,
  Cpu,
  HardDrive,
  Network,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Minus,
  Eye,
  X
} from 'lucide-react';

/**
 * System Health Monitor Dashboard
 * 
 * Features:
 * - Real-time system resource monitoring (CPU, memory, disk)
 * - Process health tracking with status indicators
 * - API endpoint health monitoring
 * - Active alerts with severity levels
 * - Alert acknowledgment and history
 * - Auto-refresh every 30 seconds
 * - Historical metrics graphs (last hour)
 */
const SystemHealthPanel = () => {
  // State
  const [systemMetrics, setSystemMetrics] = useState(null);
  const [metricsHistory, setMetricsHistory] = useState([]);
  const [processes, setProcesses] = useState({});
  const [apiStatus, setApiStatus] = useState({});
  const [activeAlerts, setActiveAlerts] = useState([]);
  const [alertHistory, setAlertHistory] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  // Dialog state
  const [alertHistoryDialogOpen, setAlertHistoryDialogOpen] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState(null);

  // Fetch all health data
  const fetchHealthData = async () => {
    try {
      setError(null);

      // Fetch summary (includes system, processes, APIs, alerts)
      const summaryRes = await fetch('/api/system-health/summary');
      if (summaryRes.ok) {
        const data = await summaryRes.json();
        setSummary(data);
      }

      // Fetch current system metrics
      let metricsData = null;
      const metricsRes = await fetch('/api/system-health/metrics');
      if (metricsRes.ok) {
        const data = await metricsRes.json();
        if (data.metrics) {
          metricsData = data.metrics;
        }
      }
      
      // Fallback to /api/health/detailed if system-health endpoints don't work
      if (!metricsData) {
        const detailedRes = await fetch('/api/health/detailed');
        if (detailedRes.ok) {
          const detailedData = await detailedRes.json();
          if (detailedData.data && detailedData.data.resources) {
            const resources = detailedData.data.resources;
            // Convert to expected format (handle both percent and percent_used)
            metricsData = {
              cpu_percent: resources.cpu?.percent || resources.cpu?.percent_used || 0,
              cpu_count: resources.cpu?.cores || 0,
              load_average_1m: resources.cpu?.load_avg_1m || resources.cpu?.load_average?.get?.(0) || 0,
              load_average_5m: resources.cpu?.load_avg_5m || resources.cpu?.load_average?.get?.(1) || 0,
              load_average_15m: resources.cpu?.load_avg_15m || resources.cpu?.load_average?.get?.(2) || 0,
              memory_percent: resources.memory?.percent_used || resources.memory?.percent || 0,
              memory_used_mb: resources.memory?.used_gb ? (resources.memory.used_gb * 1024) : 
                             (resources.memory?.total_gb && resources.memory?.available_gb ? 
                              ((resources.memory.total_gb - resources.memory.available_gb) * 1024) : 0),
              memory_total_mb: resources.memory?.total_gb ? (resources.memory.total_gb * 1024) : 0,
              disk_percent: resources.disk?.percent_used || resources.disk?.percent || 0,
              disk_used_gb: resources.disk?.used_gb || 0,
              disk_total_gb: resources.disk?.total_gb || 0
            };
          }
        }
      }
      
      if (metricsData) {
        setSystemMetrics(metricsData);
      }

      // Fetch metrics history (last hour)
      const historyRes = await fetch('/api/system-health/metrics/history?minutes=60');
      if (historyRes.ok) {
        const data = await historyRes.json();
        setMetricsHistory(data.history);
      }

      // Fetch process health
      const processRes = await fetch('/api/system-health/processes');
      if (processRes.ok) {
        const data = await processRes.json();
        setProcesses(data.processes);
      }

      // Fetch API status
      const apiRes = await fetch('/api/system-health/api-status');
      if (apiRes.ok) {
        const data = await apiRes.json();
        setApiStatus(data.apis);
      }

      // Fetch active alerts
      const alertsRes = await fetch('/api/system-health/alerts');
      if (alertsRes.ok) {
        const data = await alertsRes.json();
        setActiveAlerts(data.alerts);
      }

      setLastUpdate(new Date());
      setLoading(false);
    } catch (err) {
      console.error('Error fetching health data:', err);
      setError(err.message);
      setLoading(false);
    }
  };

  // Fetch alert history
  const fetchAlertHistory = async () => {
    try {
      const res = await fetch('/api/system-health/alerts/history?hours=24');
      if (res.ok) {
        const data = await res.json();
        setAlertHistory(data.history);
      }
    } catch (err) {
      console.error('Error fetching alert history:', err);
    }
  };

  // Acknowledge alert
  const acknowledgeAlert = async (alertId) => {
    try {
      const res = await fetch(`/api/system-health/alerts/${alertId}/acknowledge`, {
        method: 'POST'
      });
      
      if (res.ok) {
        // Refresh alerts
        fetchHealthData();
      }
    } catch (err) {
      console.error('Error acknowledging alert:', err);
    }
  };

  // Clear acknowledged alerts
  const clearAcknowledgedAlerts = async () => {
    try {
      const res = await fetch('/api/system-health/alerts/clear', {
        method: 'POST'
      });
      
      if (res.ok) {
        fetchHealthData();
      }
    } catch (err) {
      console.error('Error clearing alerts:', err);
    }
  };

  // Auto-refresh
  useEffect(() => {
    fetchHealthData();
    const interval = setInterval(fetchHealthData, 30000); // 30 seconds
    return () => clearInterval(interval);
  }, []);

  // Get severity color
  const getSeverityColor = (severity) => {
    const colors = {
      critical: 'error',
      error: 'error',
      warning: 'warning',
      info: 'info'
    };
    return colors[severity] || 'default';
  };

  // Get status color for health
  const getHealthColor = (percent) => {
    if (percent >= 95) return 'error';
    if (percent >= 80) return 'warning';
    return 'success';
  };

  // Get process status icon and color
  const getProcessStatusIcon = (status) => {
    switch (status) {
      case 'running':
        return { icon: <CheckCircle size={16} />, color: 'success' };
      case 'stopped':
        return { icon: <Minus size={16} />, color: 'default' };
      case 'crashed':
        return { icon: <XCircle size={16} />, color: 'error' };
      default:
        return { icon: <AlertTriangle size={16} />, color: 'warning' };
    }
  };

  // Get API status icon and color
  const getApiStatusIcon = (status) => {
    switch (status) {
      case 'up':
        return { icon: <CheckCircle size={16} />, color: 'success' };
      case 'down':
        return { icon: <XCircle size={16} />, color: 'error' };
      case 'degraded':
        return { icon: <AlertTriangle size={16} />, color: 'warning' };
      default:
        return { icon: <Minus size={16} />, color: 'default' };
    }
  };

  // Format bytes
  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  // Format uptime
  const formatUptime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  if (loading) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography>Loading health data...</Typography>
        <LinearProgress sx={{ mt: 2 }} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">
          <AlertTitle>Error Loading Health Data</AlertTitle>
          {error}
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Activity size={32} />
            System Health Monitor
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Real-time system monitoring with auto-healing
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {lastUpdate && (
            <Typography variant="caption" color="text.secondary">
              Last update: {lastUpdate.toLocaleTimeString()}
            </Typography>
          )}
          <IconButton onClick={fetchHealthData} color="primary">
            <RefreshCw size={20} />
          </IconButton>
        </Box>
      </Box>

      {/* Overall Health Status */}
      {summary && (
        <Alert 
          severity={
            summary.overall_health === 'healthy' ? 'success' :
            summary.overall_health === 'warning' ? 'warning' : 'error'
          }
          sx={{ mb: 3 }}
        >
          <AlertTitle>
            Overall Status: {summary.overall_health.toUpperCase()}
          </AlertTitle>
          {summary.summary.alerts.critical > 0 && (
            <Typography variant="body2">
              {summary.summary.alerts.critical} critical alert(s) active
            </Typography>
          )}
        </Alert>
      )}

      {/* Active Alerts */}
      {activeAlerts.length > 0 && (
        <Card sx={{ mb: 3, borderLeft: 4, borderColor: 'error.main' }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <AlertTriangle size={20} color="#f44336" />
                Active Alerts ({activeAlerts.length})
              </Typography>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  size="small"
                  startIcon={<Eye size={16} />}
                  onClick={() => {
                    fetchAlertHistory();
                    setAlertHistoryDialogOpen(true);
                  }}
                >
                  View History
                </Button>
                <Button
                  size="small"
                  onClick={clearAcknowledgedAlerts}
                  disabled={!activeAlerts.some(a => a.acknowledged)}
                >
                  Clear Acknowledged
                </Button>
              </Box>
            </Box>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Severity</TableCell>
                    <TableCell>Category</TableCell>
                    <TableCell>Message</TableCell>
                    <TableCell>Time</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {activeAlerts.map((alert) => (
                    <TableRow key={alert.id} sx={{ opacity: alert.acknowledged ? 0.5 : 1 }}>
                      <TableCell>
                        <Chip
                          label={alert.severity.toUpperCase()}
                          color={getSeverityColor(alert.severity)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>{alert.category}</TableCell>
                      <TableCell>{alert.message}</TableCell>
                      <TableCell>
                        {new Date(alert.timestamp).toLocaleTimeString()}
                      </TableCell>
                      <TableCell>
                        {!alert.acknowledged && (
                          <Button
                            size="small"
                            onClick={() => acknowledgeAlert(alert.id)}
                          >
                            Acknowledge
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* System Metrics */}
      <Grid container spacing={3}>
        {/* CPU */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Cpu size={20} />
                  CPU Usage
                </Typography>
                <Chip
                  label={`${(systemMetrics?.cpu_percent || 0).toFixed(1)}%`}
                  color={getHealthColor(systemMetrics?.cpu_percent || 0)}
                  size="small"
                />
              </Box>
              <LinearProgress
                variant="determinate"
                value={systemMetrics?.cpu_percent || 0}
                color={getHealthColor(systemMetrics?.cpu_percent || 0)}
                sx={{ height: 8, borderRadius: 1 }}
              />
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                {systemMetrics?.cpu_count || 'N/A'} cores
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Load: {(systemMetrics?.load_average_1m || 0).toFixed(2)} / {(systemMetrics?.load_average_5m || 0).toFixed(2)} / {(systemMetrics?.load_average_15m || 0).toFixed(2)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Memory */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Activity size={20} />
                  Memory Usage
                </Typography>
                <Chip
                  label={`${(systemMetrics?.memory_percent || 0).toFixed(1)}%`}
                  color={getHealthColor(systemMetrics?.memory_percent || 0)}
                  size="small"
                />
              </Box>
              <LinearProgress
                variant="determinate"
                value={systemMetrics?.memory_percent || 0}
                color={getHealthColor(systemMetrics?.memory_percent || 0)}
                sx={{ height: 8, borderRadius: 1 }}
              />
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                {systemMetrics?.memory_used_mb ? `${systemMetrics.memory_used_mb.toFixed(0)} MB` : 'N/A'} / {systemMetrics?.memory_total_mb ? `${systemMetrics.memory_total_mb.toFixed(0)} MB` : 'N/A'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Disk */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <HardDrive size={20} />
                  Disk Usage
                </Typography>
                <Chip
                  label={`${(systemMetrics?.disk_percent || 0).toFixed(1)}%`}
                  color={getHealthColor(systemMetrics?.disk_percent || 0)}
                  size="small"
                />
              </Box>
              <LinearProgress
                variant="determinate"
                value={systemMetrics?.disk_percent || 0}
                color={getHealthColor(systemMetrics?.disk_percent || 0)}
                sx={{ height: 8, borderRadius: 1 }}
              />
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                {systemMetrics?.disk_used_gb ? `${systemMetrics.disk_used_gb.toFixed(1)} GB` : 'N/A'} / {systemMetrics?.disk_total_gb ? `${systemMetrics.disk_total_gb.toFixed(1)} GB` : 'N/A'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Process Health */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Process Health
              </Typography>
              {Object.keys(processes).length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No monitored processes found
                </Typography>
              ) : (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Process</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>PID</TableCell>
                        <TableCell>CPU</TableCell>
                        <TableCell>Memory</TableCell>
                        <TableCell>Uptime</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {Object.entries(processes).map(([name, health]) => {
                        const statusInfo = getProcessStatusIcon(health.status);
                        return (
                          <TableRow key={name}>
                            <TableCell>{name}</TableCell>
                            <TableCell>
                              <Chip
                                icon={statusInfo.icon}
                                label={health.status}
                                color={statusInfo.color}
                                size="small"
                              />
                            </TableCell>
                            <TableCell>{health.pid || '-'}</TableCell>
                            <TableCell>{health.cpu_percent?.toFixed(1)}%</TableCell>
                            <TableCell>{health.memory_mb?.toFixed(0)} MB</TableCell>
                            <TableCell>{formatUptime(health.uptime_seconds)}</TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* API Health */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <Network size={20} />
                API Health
              </Typography>
              {Object.keys(apiStatus).length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No API endpoints monitored
                </Typography>
              ) : (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Endpoint</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Latency</TableCell>
                        <TableCell>Last Check</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {Object.entries(apiStatus).map(([endpoint, status]) => {
                        const statusInfo = getApiStatusIcon(status.status);
                        return (
                          <TableRow key={endpoint}>
                            <TableCell>
                              <Tooltip title={endpoint}>
                                <Typography variant="caption">
                                  {endpoint.length > 30 ? '...' + endpoint.slice(-27) : endpoint}
                                </Typography>
                              </Tooltip>
                            </TableCell>
                            <TableCell>
                              <Chip
                                icon={statusInfo.icon}
                                label={status.status}
                                color={statusInfo.color}
                                size="small"
                              />
                            </TableCell>
                            <TableCell>
                              {status.latency_ms ? `${status.latency_ms.toFixed(0)}ms` : '-'}
                            </TableCell>
                            <TableCell>
                              {new Date(status.last_check).toLocaleTimeString()}
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
        </Grid>
      </Grid>

      {/* Alert History Dialog */}
      <Dialog
        open={alertHistoryDialogOpen}
        onClose={() => setAlertHistoryDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          Alert History (Last 24 Hours)
        </DialogTitle>
        <DialogContent>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Time</TableCell>
                  <TableCell>Severity</TableCell>
                  <TableCell>Category</TableCell>
                  <TableCell>Message</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {alertHistory.map((alert) => (
                  <TableRow key={alert.id}>
                    <TableCell>{new Date(alert.timestamp).toLocaleString()}</TableCell>
                    <TableCell>
                      <Chip
                        label={alert.severity}
                        color={getSeverityColor(alert.severity)}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>{alert.category}</TableCell>
                    <TableCell>{alert.message}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAlertHistoryDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SystemHealthPanel;
