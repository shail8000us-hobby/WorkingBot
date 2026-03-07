/**
 * MMMAnalyticsPanel — Session Analytics & Exposure Tracking
 *
 * Institutional-level metrics dashboard showing:
 * - Session timing & duration
 * - Initial vs current vs peak exposure
 * - Cumulative trading volume
 * - Exit statistics (auto-close, manual)
 * - Risk event timeline
 * - P&L milestones
 * - Greeks tracking
 *
 * Created: February 18, 2026
 */

import React, { useState, useCallback } from 'react';
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';
import {
  Box,
  Typography,
  Grid,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Divider,
  CircularProgress,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Timeline as TimelineIcon,
  ShowChart as ChartIcon,
} from '@mui/icons-material';
import mmmService from './mmmService';

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '--';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hrs > 0) return `${hrs}h ${mins}m ${secs}s`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

function formatTimestamp(iso) {
  if (!iso) return '--';
  try {
    const dt = new Date(iso);
    return dt.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return '--';
  }
}

function MetricCard({ label, value, subtitle, color = 'primary', icon }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <Box flex={1}>
          <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.75rem', fontWeight: 600 }}>
            {label}
          </Typography>
          <Typography variant="h6" sx={{ fontFamily: 'monospace', fontWeight: 700, color: `${color}.main`, mt: 0.5 }}>
            {value}
          </Typography>
          {subtitle && (
            <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
              {subtitle}
            </Typography>
          )}
        </Box>
        {icon && (
          <Box sx={{ ml: 1, color: `${color}.main`, opacity: 0.6 }}>
            {icon}
          </Box>
        )}
      </Box>
    </Paper>
  );
}

export default function MMMAnalyticsPanel({ sessionId }) {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAnalytics = useCallback(async () => {
    if (!sessionId) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const response = await mmmService.getSessionAnalytics(sessionId);
      if (response.success) {
        setAnalytics(response.analytics);
      } else {
        setError(response.error || 'Failed to load analytics');
      }
    } catch (err) {
      setError(err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useVisibilityAwarePolling(fetchAnalytics, 30000, 120000, !!sessionId);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography color="error">Error loading analytics: {error}</Typography>
      </Box>
    );
  }

  if (!analytics) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography color="text.secondary">No analytics data available</Typography>
      </Box>
    );
  }

  // Calculate derived metrics
  const volumeTurnover = analytics.initial_ce_lots + analytics.initial_pe_lots > 0
    ? (analytics.total_combined_lots_traded / (analytics.initial_ce_lots + analytics.initial_pe_lots)).toFixed(2)
    : 0;

  return (
    <Box>
      {/* Section explainer */}
      <Typography
        variant="caption"
        sx={{ display: 'block', color: 'text.secondary', mb: 2, fontStyle: 'italic', fontSize: '0.78rem', opacity: 0.75 }}
      >
        📊 Institutional-level session analytics tracking exposure, volume, risk events, and performance milestones.
        Metrics update every heartbeat with zero impact on trading logic.
      </Typography>

      {/* Session Info */}
      <Paper variant="outlined" sx={{ p: 2, mb: 2, borderRadius: 2, bgcolor: 'action.hover' }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>Session Overview</Typography>
        <Grid container spacing={2}>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">Status</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {analytics.session_status}
            </Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">Expiry</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: 'monospace' }}>
              {analytics.expiry || '--'}
            </Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">Started</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.8rem' }}>
              {formatTimestamp(analytics.session_start_time)}
            </Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">Duration</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: 'monospace' }}>
              {formatDuration(analytics.current_duration_seconds)}
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* Exposure Metrics */}
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>Exposure Metrics</Typography>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={6} sm={4} md={2}>
          <MetricCard
            label="Initial CE"
            value={analytics.initial_ce_lots}
            subtitle="Entry lots"
            color="info"
          />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <MetricCard
            label="Initial PE"
            value={analytics.initial_pe_lots}
            subtitle="Entry lots"
            color="info"
          />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <MetricCard
            label="Current CE"
            value={analytics.current_ce_lots}
            subtitle="Open now"
            color="primary"
          />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <MetricCard
            label="Current PE"
            value={analytics.current_pe_lots}
            subtitle="Open now"
            color="primary"
          />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <MetricCard
            label="Peak CE"
            value={analytics.max_ce_lots}
            subtitle="Max exposure"
            color="warning"
            icon={<TrendingUpIcon fontSize="small" />}
          />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <MetricCard
            label="Peak PE"
            value={analytics.max_pe_lots}
            subtitle="Max exposure"
            color="warning"
            icon={<TrendingUpIcon fontSize="small" />}
          />
        </Grid>
      </Grid>

      {/* Trading Volume */}
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>Cumulative Trading Volume</Typography>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={6} sm={3}>
          <MetricCard
            label="CE Traded"
            value={analytics.total_ce_lots_traded || 0}
            subtitle={`${((analytics.total_ce_lots_traded || 0) / Math.max(analytics.initial_ce_lots, 1) * 100).toFixed(0)}% of initial`}
            color="secondary"
          />
        </Grid>
        <Grid item xs={6} sm={3}>
          <MetricCard
            label="PE Traded"
            value={analytics.total_pe_lots_traded || 0}
            subtitle={`${((analytics.total_pe_lots_traded || 0) / Math.max(analytics.initial_pe_lots, 1) * 100).toFixed(0)}% of initial`}
            color="secondary"
          />
        </Grid>
        <Grid item xs={6} sm={3}>
          <MetricCard
            label="Total Traded"
            value={analytics.total_combined_lots_traded || 0}
            subtitle={`${volumeTurnover}x turnover`}
            color="secondary"
            icon={<ChartIcon fontSize="small" />}
          />
        </Grid>
        <Grid item xs={6} sm={3}>
          <MetricCard
            label="Adjustments"
            value={analytics.total_adjustments || 0}
            subtitle={`${analytics.total_reversals || 0} reversals, ${analytics.total_shifts || 0} shifts`}
            color="secondary"
          />
        </Grid>
      </Grid>

      {/* Exit Statistics */}
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>Exit Statistics</Typography>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={6} sm={4}>
          <MetricCard
            label="Auto-Closes"
            value={(analytics.auto_close_events || []).length}
            subtitle={`${analytics.auto_close_total_lots || 0} lots closed`}
            color="success"
          />
        </Grid>
        <Grid item xs={6} sm={4}>
          <MetricCard
            label="Manual Closes"
            value={(analytics.manual_close_events || []).length}
            subtitle={`${analytics.manual_close_total_lots || 0} lots closed`}
            color="success"
          />
        </Grid>
        <Grid item xs={6} sm={4}>
          <MetricCard
            label="Total Closed"
            value={analytics.total_close_at_5 || 0}
            subtitle="via close-at-5"
            color="success"
          />
        </Grid>
        <Grid item xs={6} sm={4}>
          <MetricCard
            label="Harvested"
            value={analytics.total_harvests || 0}
            subtitle="lots freed via M1"
            color="success"
          />
        </Grid>
        <Grid item xs={6} sm={4}>
          <MetricCard
            label="Recycled"
            value={analytics.total_recycles || 0}
            subtitle="M2 operations"
            color="info"
          />
        </Grid>
      </Grid>

      {/* Risk Events & Milestones */}
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>Performance & Risk Milestones</Typography>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={6} sm={4} md={3}>
          <MetricCard
            label="Time to Profit"
            value={formatDuration(analytics.time_to_first_profit)}
            subtitle="First profitable"
            color="success"
          />
        </Grid>
        <Grid item xs={6} sm={4} md={3}>
          <MetricCard
            label="Time to Peak"
            value={formatDuration(analytics.time_to_peak_pnl)}
            subtitle="Highest P&L"
            color="success"
          />
        </Grid>
        <Grid item xs={6} sm={4} md={3}>
          <MetricCard
            label="Max Drawdown"
            value={`$${(analytics.max_drawdown_from_peak || 0).toFixed(0)}`}
            subtitle="From peak"
            color="error"
            icon={<TrendingDownIcon fontSize="small" />}
          />
        </Grid>
        <Grid item xs={6} sm={4} md={3}>
          <MetricCard
            label="Max |Δ|"
            value={(analytics.max_abs_delta || 0).toFixed(3)}
            subtitle="Peak delta exposure"
            color="warning"
          />
        </Grid>
        <Grid item xs={6} sm={4} md={3}>
          <MetricCard
            label="Both-Sides-Up"
            value={(analytics.both_sides_up_timestamps || []).length}
            subtitle="Critical events"
            color="error"
          />
        </Grid>
        <Grid item xs={6} sm={4} md={3}>
          <MetricCard
            label="Reversals"
            value={(analytics.reversal_timestamps || []).length}
            subtitle="Direction changes"
            color="warning"
          />
        </Grid>
        <Grid item xs={6} sm={4} md={3}>
          <MetricCard
            label="Shifts"
            value={(analytics.shift_timestamps || []).length}
            subtitle="Strike migrations"
            color="info"
          />
        </Grid>
        <Grid item xs={6} sm={4} md={3}>
          <MetricCard
            label="Final P&L"
            value={`$${(analytics.final_total_pnl || 0).toFixed(0)}`}
            subtitle={`${(analytics.final_realized_pnl || 0) >= 0 ? '+' : ''}$${(analytics.final_realized_pnl || 0).toFixed(0)} realized`}
            color={(analytics.final_total_pnl || 0) >= 0 ? 'success' : 'error'}
          />
        </Grid>
      </Grid>

      {/* Peak Risk Moment */}
      {analytics.peak_risk_timestamp && (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: 'warning.dark', color: 'warning.contrastText' }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
            ⚠️ Peak Risk Moment
          </Typography>
          <Typography variant="body2">
            Maximum exposure of <strong>{analytics.max_combined_lots} lots</strong> occurred at{' '}
            {formatTimestamp(analytics.peak_risk_timestamp)}
          </Typography>
        </Paper>
      )}
    </Box>
  );
}
