/**
 * MMM Analytics Summary - Institutional Compact Design
 * 
 * Professional 3-column summary cards with key metrics only.
 * Clear, scannable, institutional-grade analytics.
 * 
 * Created: February 18, 2026
 */

import React, { useState, useCallback } from 'react';
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';
import {
  Box,
  Paper,
  Grid,
  Typography,
  Chip,
  Alert,
  CircularProgress,
  IconButton,
  Tooltip,
  Divider,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import WarningIcon from '@mui/icons-material/Warning';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import mmmService from './mmmService';

const MMMAnalyticsSummary = ({ sessionId }) => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [source, setSource] = useState('');

  const fetchAnalytics = useCallback(async () => {
    if (!sessionId) {
      setLoading(false);
      setAnalytics(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await mmmService.getSessionAnalytics(sessionId);

      if (!data) {
        setError('No response from server');
        return;
      }

      if (data.success) {
        setAnalytics(data.analytics);
        setSource(data.source || 'unknown');
      } else {
        setError(data.error || 'Failed to load');
      }
    } catch (err) {
      console.error('Analytics error:', err);
      setError(err.response?.data?.error || err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useVisibilityAwarePolling(fetchAnalytics, 30000, 120000, !!sessionId);

  const formatDuration = (seconds) => {
    if (!seconds) return '--';
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${mins}m`;
  };

  const MetricBox = ({ label, value, subValue, color = 'text.primary', icon = null, warning = false }) => (
    <Box sx={{ mb: 2 }}>
      <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: 0.5 }}>
        {label}
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5, mt: 0.5 }}>
        {icon}
        <Typography variant="h6" sx={{ fontWeight: 700, color, fontSize: '1.3rem' }}>
          {value}
        </Typography>
        {warning && <WarningIcon fontSize="small" color="warning" />}
      </Box>
      {subValue && (
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.75rem' }}>
          {subValue}
        </Typography>
      )}
    </Box>
  );

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 120 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        Analytics Error: {error}
      </Alert>
    );
  }

  if (!analytics) {
    return (
      <Alert severity="info" sx={{ mb: 2 }}>
        No analytics available
      </Alert>
    );
  }

  const isPersisted = source === 'persistent_storage';
  const isHighRisk = (analytics.max_combined_lots || 0) > 100;

  return (
    <Box sx={{ mt: 2 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
            Session Analytics
          </Typography>
          {isPersisted && (
            <Tooltip title="Data persisted in SQLite - survives session deletion">
              <Chip label="PERSISTED" size="small" color="primary" variant="outlined" />
            </Tooltip>
          )}
        </Box>
        <Tooltip title="Refresh">
          <IconButton onClick={fetchAnalytics} size="small">
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Peak Risk Alert */}
      {isHighRisk && (
        <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 2, py: 0.5 }}>
          <strong>Peak Risk:</strong> {analytics.max_combined_lots} lots exposure
        </Alert>
      )}

      {/* Compact 3-Column Grid */}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Grid container spacing={3}>
          {/* Column 1: Session Info */}
          <Grid item xs={12} md={4}>
            <Typography variant="caption" sx={{ color: 'primary.main', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.65rem' }}>
              Session
            </Typography>
            <Divider sx={{ my: 1 }} />
            <MetricBox 
              label="Status" 
              value={analytics.session_status} 
              color={analytics.session_status === 'RUNNING' ? 'success.main' : 'text.secondary'}
            />
            <MetricBox 
              label="Duration" 
              value={formatDuration(analytics.current_duration_seconds || analytics.session_duration_seconds)}
              subValue={`Expiry: ${analytics.expiry || '--'}`}
            />
            <MetricBox 
              label="Final P&L" 
              value={`$${(analytics.final_total_pnl || 0).toFixed(2)}`}
              color={(analytics.final_total_pnl || 0) > 0 ? 'success.main' : 'error.main'}
            />
          </Grid>

          {/* Column 2: Exposure */}
          <Grid item xs={12} md={4}>
            <Typography variant="caption" sx={{ color: 'warning.main', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.65rem' }}>
              Exposure
            </Typography>
            <Divider sx={{ my: 1 }} />
            <MetricBox 
              label="Current Lots" 
              value={`${analytics.current_ce_lots || 0} CE / ${analytics.current_pe_lots || 0} PE`}
              subValue={`Total: ${(analytics.current_ce_lots || 0) + (analytics.current_pe_lots || 0)}`}
            />
            <MetricBox 
              label="Peak Exposure" 
              value={analytics.max_combined_lots || 0}
              subValue={`${analytics.max_ce_lots || 0} CE / ${analytics.max_pe_lots || 0} PE`}
              warning={isHighRisk}
              icon={isHighRisk ? <TrendingUpIcon fontSize="small" color="warning" /> : null}
            />
            <MetricBox 
              label="Max Drawdown" 
              value={`$${(analytics.max_drawdown_from_peak || 0).toFixed(0)}`}
              color={(analytics.max_drawdown_from_peak || 0) > 0 ? 'error.main' : 'text.secondary'}
            />
          </Grid>

          {/* Column 3: Activity */}
          <Grid item xs={12} md={4}>
            <Typography variant="caption" sx={{ color: 'info.main', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.65rem' }}>
              Activity
            </Typography>
            <Divider sx={{ my: 1 }} />
            <MetricBox 
              label="Adjustments" 
              value={analytics.total_adjustments || 0}
              subValue={`${analytics.total_reversals || 0} reversals, ${analytics.total_shifts || 0} shifts`}
            />
            <MetricBox 
              label="Traded Volume" 
              value={`${(analytics.total_ce_lots_traded || 0) + (analytics.total_pe_lots_traded || 0)}`}
              subValue={`${analytics.total_ce_lots_traded || 0} CE / ${analytics.total_pe_lots_traded || 0} PE`}
            />
            <MetricBox 
              label="Auto-Closes" 
              value={analytics.auto_close_events?.length || 0}
              subValue={`${analytics.auto_close_total_lots || 0} lots closed`}
            />
          </Grid>
        </Grid>
      </Paper>

      {/* Data Source Info */}
      {isPersisted && (
        <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <InfoOutlinedIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Analytics stored in SQLite database - persists after session deletion
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default MMMAnalyticsSummary;
