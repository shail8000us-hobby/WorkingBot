/**
 * MMM Analytics Table - Readable, Scannable Format
 * 
 * Professional table layout for session analytics.
 * Replaces scattered card grid with structured rows.
 * 
 * Created: February 18, 2026
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Chip,
  Alert,
  CircularProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import WarningIcon from '@mui/icons-material/Warning';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import mmmService from './mmmService';

const MMMAnalyticsTable = ({ sessionId }) => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [source, setSource] = useState('');

  const fetchAnalytics = async () => {
    if (!sessionId) return;

    try {
      setLoading(true);
      setError(null);
      const data = await mmmService.getSessionAnalytics(sessionId);
      
      // The service returns data directly (not wrapped in response.data)
      if (!data) {
        setError('Invalid API response');
        return;
      }
      
      if (data.success) {
        setAnalytics(data.analytics);
        setSource(data.source || 'unknown');
      } else {
        setError(data.error || 'Failed to fetch analytics');
      }
    } catch (err) {
      console.error('Analytics fetch error:', err);
      setError(err.response?.data?.error || err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
    const interval = setInterval(fetchAnalytics, 30000); // Auto-refresh every 30s
    return () => clearInterval(interval);
  }, [sessionId]);

  const formatDuration = (seconds) => {
    if (!seconds) return '--';
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${mins}m`;
  };

  const formatTimestamp = (ts) => {
    if (!ts) return '--';
    try {
      const date = new Date(ts);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return '--';
    }
  };

  const formatNumber = (num, decimals = 0) => {
    if (num === null || num === undefined) return '--';
    return Number(num).toFixed(decimals);
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        Failed to load analytics: {error}
      </Alert>
    );
  }

  if (!analytics) {
    return (
      <Alert severity="info" sx={{ m: 2 }}>
        No analytics data available
      </Alert>
    );
  }

  // Group analytics into logical sections
  const sections = [
    {
      title: 'Session Overview',
      rows: [
        { label: 'Status', value: analytics.session_status, 
          chip: true, color: analytics.session_status === 'RUNNING' ? 'success' : 'default' },
        { label: 'Expiry', value: analytics.expiry || '--' },
        { label: 'Started', value: formatTimestamp(analytics.session_start_time) },
        { label: 'Duration', value: formatDuration(analytics.current_duration_seconds || analytics.session_duration_seconds) },
        { label: 'Data Source', value: source === 'persistent_storage' ? 'Persistent' : 'Live', 
          chip: true, color: source === 'persistent_storage' ? 'primary' : 'secondary' },
      ],
    },
    {
      title: 'Exposure Metrics',
      rows: [
        { label: 'Initial CE Lots', value: formatNumber(analytics.initial_ce_lots) },
        { label: 'Initial PE Lots', value: formatNumber(analytics.initial_pe_lots) },
        { label: 'Current CE Lots', value: formatNumber(analytics.current_ce_lots), bold: true },
        { label: 'Current PE Lots', value: formatNumber(analytics.current_pe_lots), bold: true },
        { label: 'Peak CE Lots', value: formatNumber(analytics.max_ce_lots), 
          icon: analytics.max_ce_lots > analytics.initial_ce_lots ? <TrendingUpIcon fontSize="small" color="warning" /> : null },
        { label: 'Peak PE Lots', value: formatNumber(analytics.max_pe_lots),
          icon: analytics.max_pe_lots > analytics.initial_pe_lots ? <TrendingUpIcon fontSize="small" color="warning" /> : null },
        { label: 'Peak Combined', value: formatNumber(analytics.max_combined_lots), bold: true,
          highlight: analytics.max_combined_lots > 100 ? 'error' : null },
        { label: 'Peak Time', value: formatTimestamp(analytics.peak_risk_timestamp), fontSize: '0.9em' },
      ],
    },
    {
      title: 'Trading Volume',
      rows: [
        { label: 'Total CE Traded', value: formatNumber(analytics.total_ce_lots_traded) },
        { label: 'Total PE Traded', value: formatNumber(analytics.total_pe_lots_traded) },
        { label: 'Cumulative Volume', value: formatNumber(
          (analytics.total_ce_lots_traded || 0) + (analytics.total_pe_lots_traded || 0)
        ), bold: true },
        { label: 'Turnover Ratio', value: `${formatNumber(
          ((analytics.total_ce_lots_traded + analytics.total_pe_lots_traded) / 
           (analytics.initial_ce_lots + analytics.initial_pe_lots) || 0) * 100, 1
        )}%` },
      ],
    },
    {
      title: 'Adjustments & Events',
      rows: [
        { label: 'Total Adjustments', value: formatNumber(analytics.total_adjustments) },
        { label: 'Reversals', value: formatNumber(analytics.total_reversals) },
        { label: 'Strike Shifts', value: formatNumber(analytics.total_shifts) },
        { label: 'Both-Sides-Up Events', value: formatNumber(analytics.both_sides_up_timestamps?.length || 0),
          highlight: (analytics.both_sides_up_timestamps?.length || 0) > 0 ? 'warning' : null },
        { label: 'Auto-Closes', value: formatNumber(analytics.auto_close_events?.length || 0) },
        { label: 'Auto-Close Lots', value: formatNumber(analytics.auto_close_total_lots) },
      ],
    },
    {
      title: 'Performance & Risk',
      rows: [
        { label: 'Time to Profit', value: formatDuration(analytics.time_to_first_profit) },
        { label: 'Max Drawdown', value: `$${formatNumber(analytics.max_drawdown_from_peak)}`,
          highlight: analytics.max_drawdown_from_peak > 0 ? 'error' : null },
        { label: 'Max |Δ|', value: formatNumber(analytics.max_abs_delta, 3),
          highlight: analytics.max_abs_delta > 0.5 ? 'warning' : null },
        { label: 'Final P&L', value: `$${formatNumber(analytics.final_total_pnl)}`,
          color: analytics.final_total_pnl > 0 ? 'success' : 'error', bold: true },
      ],
    },
  ];

  return (
    <Box sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">
          Session Analytics
        </Typography>
        <Tooltip title="Refresh analytics">
          <IconButton onClick={fetchAnalytics} size="small">
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Peak Risk Alert */}
      {analytics.max_combined_lots > 100 && (
        <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 2 }}>
          <strong>Peak Risk:</strong> {analytics.max_combined_lots} lots at{' '}
          {formatTimestamp(analytics.peak_risk_timestamp)}
        </Alert>
      )}

      {/* Analytics Tables */}
      {sections.map((section) => (
        <Box key={section.title} sx={{ mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: 'text.secondary' }}>
            {section.title}
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableBody>
                {section.rows.map((row, idx) => (
                  <TableRow 
                    key={idx}
                    sx={{ 
                      '&:hover': { bgcolor: 'action.hover' },
                      ...(row.highlight && { bgcolor: `${row.highlight}.light` })
                    }}
                  >
                    <TableCell 
                      sx={{ 
                        fontWeight: 500, 
                        width: '50%',
                        fontSize: row.fontSize || 'inherit'
                      }}
                    >
                      {row.label}
                    </TableCell>
                    <TableCell 
                      align="right"
                      sx={{ 
                        fontWeight: row.bold ? 700 : 400,
                        fontSize: row.fontSize || 'inherit',
                        color: row.color ? `${row.color}.main` : 'inherit'
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
                        {row.icon}
                        {row.chip ? (
                          <Chip label={row.value} size="small" color={row.color || 'default'} />
                        ) : (
                          row.value
                        )}
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      ))}

      {/* Data Persistence Notice */}
      {source === 'persistent_storage' && (
        <Alert severity="info" sx={{ mt: 2 }}>
          <strong>Persistent Data:</strong> This analytics record is stored separately and survives session deletion.
        </Alert>
      )}
    </Box>
  );
};

export default MMMAnalyticsTable;
