import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  Button,
  Alert,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  CircularProgress,
  Tooltip,
  TextField,
  InputAdornment,
  Card,
  CardContent,
  Grid,
  IconButton,
} from '@mui/material';
import {
  Sync as SyncIcon,
  Warning as WarningIcon,
  CloudDownload as CloudDownloadIcon,
  Refresh as RefreshIcon,
  Search as SearchIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  PlayArrow as PlayArrowIcon,
  GetApp as GetAppIcon,
  DeleteSweep as DeleteSweepIcon,
} from '@mui/icons-material';
import { useSocket } from '../hooks/useSocket';
import apiClient from '../utils/robustApiClient';

const formatNumber = (value) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  if (typeof value === 'number') return Number.isInteger(value) ? value : value.toFixed(4);
  return value;
};

// Productivity Metrics Component
const ProductivityMetricsCard = ({ metrics, detectionSummary }) => {
  if (!metrics) return null;
  
  const {
    productivity_score = 0,
    capital_utilization_pct = 0,
    order_success_rate_pct = 0,
    missed_fills_count = 0,
    avg_heal_time_seconds = 0,
    uptime_pct = 0,
    capital_freed_usd = 0,
    profit_recovered_usd = 0,
  } = metrics;
  
  const getScoreColor = (score) => {
    if (score >= 90) return 'success';
    if (score >= 70) return 'warning';
    return 'error';
  };
  
  const getHealthIcon = (status) => {
    switch (status) {
      case 'healthy': return <CheckCircleIcon sx={{ color: 'success.main' }} />;
      case 'minor_issues': return <InfoIcon sx={{ color: 'warning.main' }} />;
      case 'needs_attention': return <WarningIcon sx={{ color: 'warning.main' }} />;
      case 'critical': return <ErrorIcon sx={{ color: 'error.main' }} />;
      default: return <InfoIcon />;
    }
  };
  
  return (
    <Card sx={{ mb: 2, bgcolor: 'background.paper' }}>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            {detectionSummary && getHealthIcon(detectionSummary.health_status)}
            <Typography variant="h6">
              Bot Productivity Score
            </Typography>
          </Box>
          <Chip 
            label={`${productivity_score}/100`}
            color={getScoreColor(productivity_score)}
            size="large"
            sx={{ fontSize: '1.1rem', fontWeight: 'bold' }}
          />
        </Box>
        
        <Grid container spacing={2}>
          <Grid item xs={6} sm={3}>
            <Box textAlign="center" p={1}>
              <Typography variant="caption" color="text.secondary">
                Capital Utilization
              </Typography>
              <Typography variant="h6" color={capital_utilization_pct >= 80 ? 'success.main' : 'warning.main'}>
                {capital_utilization_pct.toFixed(1)}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {capital_utilization_pct >= 80 ? 'Good' : 'Low'}
              </Typography>
            </Box>
          </Grid>
          
          <Grid item xs={6} sm={3}>
            <Box textAlign="center" p={1}>
              <Typography variant="caption" color="text.secondary">
                Order Success Rate
              </Typography>
              <Typography variant="h6" color={order_success_rate_pct >= 95 ? 'success.main' : 'warning.main'}>
                {order_success_rate_pct.toFixed(1)}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {order_success_rate_pct >= 95 ? 'Excellent' : 'Needs Work'}
              </Typography>
            </Box>
          </Grid>
          
          <Grid item xs={6} sm={3}>
            <Box textAlign="center" p={1}>
              <Typography variant="caption" color="text.secondary">
                Missed Fills
              </Typography>
              <Typography variant="h6" color={missed_fills_count === 0 ? 'success.main' : 'error.main'}>
                {missed_fills_count}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Last Hour
              </Typography>
            </Box>
          </Grid>
          
          <Grid item xs={6} sm={3}>
            <Box textAlign="center" p={1}>
              <Typography variant="caption" color="text.secondary">
                Uptime
              </Typography>
              <Typography variant="h6" color="success.main">
                {uptime_pct.toFixed(1)}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                24 Hours
              </Typography>
            </Box>
          </Grid>
        </Grid>
        
        {(capital_freed_usd > 0 || profit_recovered_usd > 0) && (
          <Box mt={2} p={2} bgcolor="success.dark" borderRadius={1}>
            <Typography variant="subtitle2" gutterBottom>
              💰 Value Recovered This Session
            </Typography>
            <Grid container spacing={2}>
              {capital_freed_usd > 0 && (
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Capital Freed:
                  </Typography>
                  <Typography variant="h6" color="success.light">
                    ${capital_freed_usd.toFixed(2)}
                  </Typography>
                </Grid>
              )}
              {profit_recovered_usd > 0 && (
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Profit Recovered:
                  </Typography>
                  <Typography variant="h6" color="success.light">
                    ${profit_recovered_usd.toFixed(2)}
                  </Typography>
                </Grid>
              )}
            </Grid>
          </Box>
        )}
        
        {detectionSummary?.recommendation && (
          <Alert 
            severity={detectionSummary.health_status === 'healthy' ? 'success' : 'warning'}
            sx={{ mt: 2 }}
          >
            {detectionSummary.recommendation}
          </Alert>
        )}
      </CardContent>
    </Card>
  );
};

// Historical Insights Component
const HistoricalInsightsCard = () => {
  const [insights, setInsights] = React.useState(null);
  const [trends, setTrends] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [selectedPeriod, setSelectedPeriod] = React.useState('last_24h');

  const fetchData = React.useCallback(async () => {
    try {
      setLoading(true);
      const [insightsData, trendsData] = await Promise.all([
        apiClient.get('/api/recon/insights'),
        apiClient.get('/api/recon/trends', { params: { period: selectedPeriod } })
      ]);
      setInsights(insightsData.insights);
      setTrends(trendsData.trends);
    } catch (err) {
      console.error('Failed to load insights:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedPeriod]);

  React.useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box display="flex" justifyContent="center" p={2}>
            <CircularProgress size={24} />
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (!insights || !trends) return null;

  const getHealthColor = (score) => {
    if (score >= 90) return 'success.main';
    if (score >= 70) return 'warning.main';
    return 'error.main';
  };

  const getTrendIcon = (direction) => {
    switch (direction) {
      case 'improving': return <CheckCircleIcon sx={{ color: 'success.main' }} />;
      case 'degrading': return <WarningIcon sx={{ color: 'error.main' }} />;
      default: return <InfoIcon sx={{ color: 'info.main' }} />;
    }
  };

  return (
    <Card sx={{ mb: 2, bgcolor: 'background.paper' }}>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <InfoIcon color="primary" />
            <Typography variant="h6">
              Historical Insights & Trends
            </Typography>
          </Box>
          <Box display="flex" gap={1}>
            {['last_hour', 'last_24h', 'last_7d', 'last_30d'].map((period) => (
              <Button
                key={period}
                size="small"
                variant={selectedPeriod === period ? 'contained' : 'outlined'}
                onClick={() => setSelectedPeriod(period)}
                sx={{ minWidth: 60, textTransform: 'none' }}
              >
                {period.replace('last_', '').replace('h', 'h').replace('d', 'd')}
              </Button>
            ))}
          </Box>
        </Box>

        <Grid container spacing={2}>
          {/* Health Score */}
          <Grid item xs={12} sm={6} md={3}>
            <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default', textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                System Health Score
              </Typography>
              <Typography variant="h3" sx={{ color: getHealthColor(insights.health_score), fontWeight: 'bold' }}>
                {insights.health_score}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                / 100
              </Typography>
            </Paper>
          </Grid>

          {/* Trend Direction */}
          <Grid item xs={12} sm={6} md={3}>
            <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default', textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                Trend Direction
              </Typography>
              <Box display="flex" alignItems="center" justifyContent="center" gap={1} mt={1}>
                {getTrendIcon(trends.trend_direction)}
                <Typography variant="h6" sx={{ textTransform: 'capitalize' }}>
                  {trends.trend_direction}
                </Typography>
              </Box>
              <Typography variant="caption" color="text.secondary">
                {trends.total_issues} issues in period
              </Typography>
            </Paper>
          </Grid>

          {/* Resolution Rate */}
          <Grid item xs={12} sm={6} md={3}>
            <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default', textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                Resolution Rate
              </Typography>
              <Typography 
                variant="h3" 
                sx={{ 
                  color: trends.resolution_rate_pct >= 80 ? 'success.main' : 'warning.main',
                  fontWeight: 'bold' 
                }}
              >
                {trends.resolution_rate_pct.toFixed(0)}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {trends.avg_resolution_time_seconds > 0 
                  ? `Avg: ${trends.avg_resolution_time_seconds.toFixed(1)}s` 
                  : 'No resolutions yet'}
              </Typography>
            </Paper>
          </Grid>

          {/* Capital Protected */}
          <Grid item xs={12} sm={6} md={3}>
            <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default', textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                Capital Protected
              </Typography>
              <Typography variant="h4" sx={{ color: 'success.main', fontWeight: 'bold' }}>
                ${insights.capital_protected_usd.toFixed(2)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {insights.issues_prevented_count} issues prevented
              </Typography>
            </Paper>
          </Grid>
        </Grid>

        {/* Recurring Issues Alert */}
        {trends.recurring_issues && trends.recurring_issues.length > 0 && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            <Typography variant="subtitle2" fontWeight="bold">
              ⚠️ Recurring Issues Detected ({trends.recurring_issues.length})
            </Typography>
            {trends.recurring_issues.slice(0, 3).map((issue, idx) => (
              <Typography key={idx} variant="caption" display="block">
                • {issue.issue_type}: Order {issue.order_id} ({issue.count}x)
              </Typography>
            ))}
          </Alert>
        )}

        {/* Peak Hours */}
        {trends.peak_issue_hours && trends.peak_issue_hours.length > 0 && (
          <Box mt={2} p={2} bgcolor="info.dark" borderRadius={1}>
            <Typography variant="subtitle2" gutterBottom>
              📊 Peak Issue Hours
            </Typography>
            <Typography variant="body2">
              Most issues occur at: {trends.peak_issue_hours.map(h => `${h}:00`).join(', ')} UTC
            </Typography>
          </Box>
        )}

        {/* Top Improvements */}
        {insights.top_improvements && insights.top_improvements.length > 0 && (
          <Box mt={2}>
            <Typography variant="subtitle2" gutterBottom>
              💪 Strengths
            </Typography>
            {insights.top_improvements.map((improvement, idx) => (
              <Typography key={idx} variant="body2" color="success.main">
                {improvement}
              </Typography>
            ))}
          </Box>
        )}

        {/* Areas Needing Attention */}
        {insights.areas_needing_attention && insights.areas_needing_attention.length > 0 && (
          <Box mt={2}>
            <Typography variant="subtitle2" gutterBottom>
              🎯 Areas to Improve
            </Typography>
            {insights.areas_needing_attention.map((area, idx) => (
              <Typography key={idx} variant="body2" color="warning.main">
                {area}
              </Typography>
            ))}
          </Box>
        )}

        {/* Recommendations */}
        {insights.recommendations && insights.recommendations.length > 0 && (
          <Box mt={2}>
            <Typography variant="subtitle2" gutterBottom>
              💡 Recommendations
            </Typography>
            {insights.recommendations.map((rec, idx) => (
              <Typography key={idx} variant="body2" color="text.secondary">
                • {rec}
              </Typography>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

// Issues List Component
const IssuesListCard = ({ issues = [], onAutoHeal }) => {
  const [healing, setHealing] = React.useState(false);
  const [dryRunMode, setDryRunMode] = React.useState(true);
  
  if (!issues || issues.length === 0) {
    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <CheckCircleIcon color="success" />
            <Typography variant="h6">
              Detected Issues
            </Typography>
          </Box>
          <Alert severity="success">
            ✅ No issues detected! All systems healthy.
          </Alert>
        </CardContent>
      </Card>
    );
  }
  
  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return 'error';
      case 'high': return 'warning';
      case 'medium': return 'info';
      case 'low': return 'default';
      default: return 'default';
    }
  };
  
  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'critical': return <ErrorIcon />;
      case 'high': return <WarningIcon />;
      default: return <InfoIcon />;
    }
  };
  
  const autoHealableIssues = issues.filter(i => i.auto_healable);
  
  const handleAutoHeal = async () => {
    if (autoHealableIssues.length === 0) return;
    
    setHealing(true);
    try {
      await onAutoHeal(issues, dryRunMode);
    } finally {
      setHealing(false);
    }
  };
  
  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <WarningIcon color="warning" />
            <Typography variant="h6">
              Detected Issues ({issues.length})
            </Typography>
          </Box>
          <Box display="flex" alignItems="center" gap={1}>
            {autoHealableIssues.length > 0 && (
              <>
                <Chip 
                  label={`${autoHealableIssues.length} Auto-Healable`}
                  color="success"
                  size="small"
                />
                <Button
                  variant={dryRunMode ? "outlined" : "contained"}
                  color={dryRunMode ? "info" : "success"}
                  size="small"
                  onClick={handleAutoHeal}
                  disabled={healing}
                  startIcon={healing ? <CircularProgress size={16} /> : <CheckCircleIcon />}
                >
                  {healing ? 'Healing...' : dryRunMode ? 'Preview Auto-Heal' : '⚡ Auto-Heal Now'}
                </Button>
                <Button
                  variant="text"
                  size="small"
                  onClick={() => setDryRunMode(!dryRunMode)}
                >
                  {dryRunMode ? '🔍 Dry Run ON' : '🚀 Live Mode'}
                </Button>
              </>
            )}
          </Box>
        </Box>
        
        <Box display="flex" flexDirection="column" gap={1}>
          {issues.map((issue, index) => (
            <Paper 
              key={index} 
              elevation={1} 
              sx={{ 
                p: 2, 
                border: '1px solid',
                borderColor: `${getSeverityColor(issue.severity)}.main`,
                bgcolor: 'background.default'
              }}
            >
              <Box display="flex" alignItems="flex-start" justifyContent="space-between" mb={1}>
                <Box display="flex" alignItems="center" gap={1}>
                  {getSeverityIcon(issue.severity)}
                  <Typography variant="subtitle2" fontWeight="bold">
                    {issue.issue_type.replace(/_/g, ' ').toUpperCase()}
                  </Typography>
                  <Chip 
                    label={issue.severity.toUpperCase()}
                    color={getSeverityColor(issue.severity)}
                    size="small"
                  />
                  {issue.auto_healable && (
                    <Chip label="Auto-Healable" color="success" size="small" variant="outlined" />
                  )}
                </Box>
                <Typography variant="caption" color="text.secondary">
                  Order: {issue.order_id || issue.client_order_id || 'N/A'}
                </Typography>
              </Box>
              
              <Typography variant="body2" color="text.secondary" mb={1}>
                {issue.description}
              </Typography>
              
              <Box display="flex" flexWrap="wrap" gap={1} alignItems="center">
                <Chip 
                  label={`Impact: ${issue.impact}`}
                  size="small"
                  variant="outlined"
                />
                {issue.metadata?.side && (
                  <Chip 
                    label={issue.metadata.side}
                    size="small"
                    color={issue.metadata.side === 'BUY' ? 'success' : 'error'}
                    variant="outlined"
                  />
                )}
                {issue.metadata?.symbol && (
                  <Chip 
                    label={issue.metadata.symbol}
                    size="small"
                    variant="outlined"
                  />
                )}
              </Box>
              
              <Alert severity="info" sx={{ mt: 1 }}>
                💡 <strong>Action:</strong> {issue.action_recommendation}
              </Alert>
            </Paper>
          ))}
        </Box>
      </CardContent>
    </Card>
  );
};

const ReconciliationPanelV2 = ({ featureFlags = {} }) => {
  const socket = useSocket();
  const [status, setStatus] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [tableLoading, setTableLoading] = useState(false);
  const [error, setError] = useState(null);
  const [records, setRecords] = useState([]);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [selectedFilter, setSelectedFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [paginationMeta, setPaginationMeta] = useState({ total: 0, totalPages: 0 });
  const [running, setRunning] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [successMessage, setSuccessMessage] = useState(null);

  const counters = status?.counters || {};
  const totalOrders = counters.total_orders || 0;
  const botOrders = counters.bot_orders || 0;
  const manualOrders = counters.manual_orders || 0;

  const refreshStatus = useCallback(async () => {
    try {
      setLoadingStatus(true);
      const data = await apiClient.get('/api/recon/status');
      setStatus(data);
      setError(null);
    } catch (err) {
      console.error('Failed to load reconciliation status:', err);
      setError(err.message);
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  const fetchRecords = useCallback(async () => {
    try {
      setTableLoading(true);
      const params = {
        filter: selectedFilter !== 'all' ? selectedFilter : undefined,
        search: debouncedSearch || undefined,
        page: page + 1,
        per_page: rowsPerPage,
      };
      const data = await apiClient.get('/api/recon/table', { params });
      setRecords(data.records || []);
      setPaginationMeta({ 
        total: data.pagination?.total || 0, 
        totalPages: data.pagination?.total_pages || 0 
      });
      setError(null);
    } catch (err) {
      console.error('Failed to load reconciliation mismatches:', err);
      setError(err.message);
    } finally {
      setTableLoading(false);
    }
  }, [selectedFilter, debouncedSearch, page, rowsPerPage]);

  const handleRunNow = async () => {
    try {
      setRunning(true);
      await apiClient.post('/api/recon/run');
      await refreshStatus();
      await fetchRecords();
    } catch (err) {
      console.error('Failed to trigger reconciliation run:', err);
      setError(err.message);
    } finally {
      setRunning(false);
    }
  };

  const handleExport = async () => {
    try {
      const data = await apiClient.get('/api/recon/status');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `reconciliation_${Date.now()}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export:', err);
      setError(err.message);
    }
  };

  const handleAutoHeal = async (issues, dryRun = true) => {
    try {
      const response = await apiClient.post('/api/recon/auto-heal', {
        issues,
        dry_run: dryRun
      });
      
      if (dryRun) {
        // Show preview
        const { would_heal, would_skip, message } = response;
        setSuccessMessage(
          `Preview: ${message}. ` +
          `Would heal ${would_heal} issues, skip ${would_skip} requiring manual review.`
        );
      } else {
        // Show actual results
        const { healed_count, skipped_count, backup_path } = response;
        setSuccessMessage(
          `✅ Auto-heal complete! Healed ${healed_count} issues, ` +
          `skipped ${skipped_count} requiring manual review. ` +
          `Backup saved to: ${backup_path}`
        );
        // Refresh data
        await refreshStatus();
        await fetchRecords();
      }
    } catch (err) {
      console.error('Auto-heal failed:', err);
      setError(err.message);
    }
  };

  const handleClearBotMemory = async () => {
    if (!window.confirm(
      '🧹 Smart Clear Bot Memory?\n\n' +
      'This will:\n' +
      '✅ KEEP all OPEN orders (won\'t break active trades)\n' +
      '🗑️  REMOVE all CLOSED/FILLED/CANCELLED orders (old data)\n' +
      '💾 CREATE automatic backup\n' +
      '⚠️  Does NOT affect volatility recovery system\n\n' +
      'Continue?'
    )) {
      return;
    }

    try {
      setClearing(true);
      setError(null);
      setSuccessMessage(null);
      
      const response = await apiClient.post('/api/recon/clear-bot-memory');
      
      if (response.success) {
        const msg = response.kept_orders > 0 
          ? `✅ Cleared ${response.cleared_orders} old orders, kept ${response.kept_orders} open orders`
          : `✅ ${response.message}`;
        setSuccessMessage(msg);
        
        // Refresh data after clearing
        await refreshStatus();
        await fetchRecords();
        
        // Clear success message after 8 seconds
        setTimeout(() => setSuccessMessage(null), 8000);
      } else {
        setError(response.error || 'Failed to clear bot memory');
      }
    } catch (err) {
      console.error('Failed to clear bot memory:', err);
      setError(err.message || 'Failed to clear bot memory');
    } finally {
      setClearing(false);
    }
  };

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm.trim()), 350);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => {
    setPage(0);
  }, [selectedFilter, debouncedSearch]);

  useEffect(() => {
    if (!socket) return;
    const handleUpdate = () => {
      refreshStatus();
      fetchRecords();
    };
    socket.on('reconciliation_update', handleUpdate);
    return () => socket.off('reconciliation_update', handleUpdate);
  }, [socket, refreshStatus, fetchRecords]);

  if (loadingStatus && !status) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" sx={{ py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <SyncIcon sx={{ fontSize: 28 }} />
            Sync & Reconciliation
            {status?.cached && (
              <Chip 
                label="⚡ Cached" 
                size="small" 
                color="success" 
                variant="outlined"
                sx={{ height: 22, fontSize: '0.7rem' }}
              />
            )}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Ensure bot, exchange, and ledger remain consistent
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Tooltip title="Refresh status">
            <IconButton onClick={refreshStatus} disabled={loadingStatus}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={running ? <CircularProgress size={18} color="inherit" /> : <PlayArrowIcon />}
            onClick={handleRunNow}
            disabled={running}
            sx={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              '&:hover': {
                background: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
              },
            }}
          >
            {running ? 'Running...' : 'Run Reconciliation Now'}
          </Button>
          <Button
            variant="outlined"
            color="warning"
            startIcon={clearing ? <CircularProgress size={18} color="inherit" /> : <DeleteSweepIcon />}
            onClick={handleClearBotMemory}
            disabled={clearing || !status}
            sx={{
              borderColor: '#FF9800',
              color: '#FF9800',
              '&:hover': {
                borderColor: '#F57C00',
                bgcolor: 'rgba(255, 152, 0, 0.08)',
              },
            }}
          >
            {clearing ? 'Clearing...' : 'Clear Bot Memory'}
          </Button>
          <Button
            variant="outlined"
            startIcon={<GetAppIcon />}
            onClick={handleExport}
          >
            Export Report
          </Button>
        </Box>
      </Box>

      {/* Dry Run Alert */}
      {featureFlags?.reconciliation_v2_dry_run && (
        <Alert severity="info" sx={{ mb: 3 }} icon={<InfoIcon />}>
          <strong>Dry Run Mode:</strong> Snapshot generation will not mutate local state
        </Alert>
      )}

      {/* Success Message */}
      {successMessage && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          <strong>Error:</strong> {error}
        </Alert>
      )}

      {/* NEW: Productivity Metrics */}
      {status && (
        <ProductivityMetricsCard 
          metrics={status?.metrics} 
          detectionSummary={status?.detection_summary}
        />
      )}

      {/* NEW: Historical Insights */}
      {status && (
        <HistoricalInsightsCard />
      )}

      {/* NEW: Detected Issues */}
      {status && (
        <IssuesListCard issues={status?.issues} onAutoHeal={handleAutoHeal} />
      )}

      {/* No Sync Data */}
      {!status && !loadingStatus && (
        <Paper sx={{ p: 6, textAlign: 'center', bgcolor: 'rgba(255, 255, 255, 0.02)' }}>
          <SyncIcon sx={{ fontSize: 60, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" gutterBottom color="text.secondary">
            No sync data available yet
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            The bot takes 60 seconds during startup to reconcile its state with the exchange
          </Typography>
          <Button
            variant="contained"
            startIcon={<PlayArrowIcon />}
            onClick={handleRunNow}
            disabled={running}
          >
            Start the bot to see sync & reconciliation data
          </Button>
        </Paper>
      )}
    </Box>
  );
};

export default ReconciliationPanelV2;
