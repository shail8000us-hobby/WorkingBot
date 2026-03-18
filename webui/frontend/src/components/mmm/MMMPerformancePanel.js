import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, Paper, Grid, Chip, LinearProgress,
  IconButton, Tooltip, CircularProgress,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import mmmService from './mmmService';

// Score color mapping
const getScoreColor = (score) => {
  if (score >= 8) return '#4caf50';
  if (score >= 6) return '#8bc34a';
  if (score >= 4) return '#ff9800';
  if (score >= 2) return '#f44336';
  return '#9e9e9e';
};

const getExitColor = (quality) => {
  if (quality === 'CLEAN') return '#4caf50';
  if (quality === 'MODERATE') return '#ff9800';
  if (quality === 'RUNNING') return '#2196f3';
  return '#f44336';
};

const ScoreGauge = ({ score, maxScore = 10 }) => {
  const pct = Math.min(100, (score / maxScore) * 100);
  const color = getScoreColor(score);
  return (
    <Box sx={{ textAlign: 'center' }}>
      <Typography variant="h3" sx={{ fontWeight: 700, color, fontFamily: 'monospace' }}>
        {score}
      </Typography>
      <Typography variant="caption" color="text.secondary">/ {maxScore}</Typography>
      <LinearProgress
        variant="determinate"
        value={pct}
        sx={{
          mt: 1, height: 8, borderRadius: 4,
          bgcolor: 'rgba(255,255,255,0.08)',
          '& .MuiLinearProgress-bar': { bgcolor: color, borderRadius: 4 },
        }}
      />
    </Box>
  );
};

const MetricCard = ({ label, value, subtitle, color }) => (
  <Paper sx={{ p: 1.5, bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 1 }}>
    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
      {label}
    </Typography>
    <Typography
      variant="h6"
      sx={{ fontWeight: 600, fontFamily: 'monospace', color: color || 'text.primary', mt: 0.25 }}
    >
      {value}
    </Typography>
    {subtitle && (
      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
        {subtitle}
      </Typography>
    )}
  </Paper>
);

const MMMPerformancePanel = ({ sessionId }) => {
  const [perf, setPerf] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPerformance = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await mmmService.getSessionPerformance(sessionId);
      if (res.success) {
        setPerf(res.performance);
      } else {
        setError(res.error || 'Failed to load');
      }
    } catch (e) {
      setError(e.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => { fetchPerformance(); }, [fetchPerformance]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress size={28} />
      </Box>
    );
  }

  if (error || !perf) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography color="text.secondary">
          {error || 'No performance data available. Data is generated when a session ends.'}
        </Typography>
      </Box>
    );
  }

  const effColor = perf.adjustment_efficiency >= 60 ? '#4caf50' :
    perf.adjustment_efficiency >= 40 ? '#ff9800' : '#f44336';

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          Performance Intelligence
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip
            label={perf.source === 'persistent_storage' ? 'Final' : 'Live'}
            size="small"
            color={perf.source === 'persistent_storage' ? 'success' : 'warning'}
            variant="outlined"
            sx={{ fontSize: '0.65rem', height: 20 }}
          />
          <Tooltip title="Refresh">
            <IconButton size="small" onClick={fetchPerformance}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Row 1: Session Score + Key Metrics */}
      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid item xs={12} sm={4}>
          <Paper sx={{ p: 2, bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 1, textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Session Score</Typography>
            <ScoreGauge score={perf.session_score} />
          </Paper>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Paper sx={{ p: 2, bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 1, textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Adjustment Efficiency</Typography>
            <Typography variant="h3" sx={{ fontWeight: 700, color: effColor, fontFamily: 'monospace', mt: 1 }}>
              {perf.adjustment_efficiency}%
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {perf.good_adjustments}G / {perf.bad_adjustments}B / {perf.total_adjustments} total
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Paper sx={{ p: 2, bgcolor: 'rgba(255,255,255,0.03)', borderRadius: 1, textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Exit Quality</Typography>
            <Typography variant="h3" sx={{ fontWeight: 700, color: getExitColor(perf.exit_quality), fontFamily: 'monospace', mt: 1 }}>
              {perf.exit_quality}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {perf.exit_quality === 'RUNNING' ? 'session still active' : `${perf.exit_pct_closed}% closed gracefully`}
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Row 2: P&L Breakdown */}
      <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block', fontWeight: 600 }}>
        P&L Breakdown
      </Typography>
      <Grid container spacing={1} sx={{ mb: 2 }}>
        <Grid item xs={6} sm={3}>
          <MetricCard
            label="Total P&L"
            value={`$${perf.total_pnl?.toFixed(2)}`}
            color={perf.total_pnl >= 0 ? '#4caf50' : '#f44336'}
          />
        </Grid>
        <Grid item xs={6} sm={3}>
          <MetricCard
            label="Realized P&L"
            value={`$${perf.realized_pnl?.toFixed(2)}`}
            color={perf.realized_pnl >= 0 ? '#4caf50' : '#f44336'}
          />
        </Grid>
        <Grid item xs={6} sm={3}>
          <MetricCard
            label="Peak P&L"
            value={`$${perf.peak_pnl?.toFixed(2)}`}
            color="#2196f3"
          />
        </Grid>
        <Grid item xs={6} sm={3}>
          <MetricCard
            label="Max Drawdown"
            value={`$${perf.max_drawdown?.toFixed(2)}`}
            color="#f44336"
          />
        </Grid>
      </Grid>

      {/* Row 3: Phase P&L */}
      <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block', fontWeight: 600 }}>
        Phase P&L (Entry / Active / Exit)
      </Typography>
      <Grid container spacing={1} sx={{ mb: 2 }}>
        <Grid item xs={4}>
          <MetricCard
            label="Entry Phase (0-20%)"
            value={`$${perf.entry_pnl?.toFixed(2)}`}
            color={perf.entry_pnl >= 0 ? '#4caf50' : '#f44336'}
          />
        </Grid>
        <Grid item xs={4}>
          <MetricCard
            label="Active Phase (20-70%)"
            value={`$${perf.active_pnl?.toFixed(2)}`}
            color={perf.active_pnl >= 0 ? '#4caf50' : '#f44336'}
          />
        </Grid>
        <Grid item xs={4}>
          <MetricCard
            label="Exit Phase (70-100%)"
            value={`$${perf.exit_pnl?.toFixed(2)}`}
            color={perf.exit_pnl >= 0 ? '#4caf50' : '#f44336'}
          />
        </Grid>
      </Grid>

      {/* Row 4: Session Info */}
      <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block', fontWeight: 600 }}>
        Session Info
      </Typography>
      <Grid container spacing={1}>
        <Grid item xs={6} sm={3}>
          <MetricCard label="Duration" value={`${perf.duration_minutes?.toFixed(0)} min`} />
        </Grid>
        <Grid item xs={6} sm={3}>
          <MetricCard label="Adjustments" value={perf.total_adjustments} />
        </Grid>
        <Grid item xs={6} sm={3}>
          <MetricCard label="Good Adj." value={perf.good_adjustments} color="#4caf50" />
        </Grid>
        <Grid item xs={6} sm={3}>
          <MetricCard label="Bad Adj." value={perf.bad_adjustments} color="#f44336" />
        </Grid>
      </Grid>
    </Box>
  );
};

export default MMMPerformancePanel;
