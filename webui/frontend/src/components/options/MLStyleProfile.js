/**
 * ML Style Profile Panel
 * 
 * Phase 2 of ML Autonomous Trading Engine
 * Shows the trader's "Trading DNA" - their style profile extracted from trades
 * 
 * Created: January 17, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  CircularProgress,
  Alert,
  Chip,
  Divider,
  Grid,
  LinearProgress,
  Tooltip,
  IconButton,
  Collapse,
  Paper,
} from '@mui/material';
import {
  Fingerprint,
  Psychology,
  TrendingUp,
  TrendingDown,
  CheckCircle,
  Refresh,
  ExpandMore,
  ExpandLess,
  AccessTime,
  ShowChart,
  AttachMoney,
  Speed,
  Warning,
  EmojiEvents,
} from '@mui/icons-material';

const fetchAPI = async (url, options = {}) => {
  const response = await fetch(url, options);
  return response.json();
};

// Radar chart component for style visualization
const StyleRadar = ({ profile }) => {
  if (!profile) return null;
  
  const traits = [
    { label: 'Risk Appetite', value: profile.risk_appetite || 0.5 },
    { label: 'Consistency', value: profile.risk_consistency || 0.5 },
    { label: 'Patience', value: profile.patience_factor || 0.5 },
    { label: 'Call Bias', value: profile.call_preference || 0.5 },
    { label: 'Buy Bias', value: profile.buy_preference || 0.5 },
  ];
  
  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="subtitle2" gutterBottom align="center">
        Trading Style DNA
      </Typography>
      <Grid container spacing={1}>
        {traits.map((trait) => (
          <Grid item xs={12} key={trait.label}>
            <Box display="flex" alignItems="center" gap={1}>
              <Typography variant="caption" sx={{ minWidth: 100 }}>
                {trait.label}
              </Typography>
              <Box sx={{ flexGrow: 1 }}>
                <LinearProgress
                  variant="determinate"
                  value={trait.value * 100}
                  sx={{
                    height: 8,
                    borderRadius: 1,
                    bgcolor: 'action.hover',
                    '& .MuiLinearProgress-bar': {
                      bgcolor: trait.value > 0.6 ? 'success.main' : trait.value < 0.4 ? 'error.main' : 'warning.main',
                    },
                  }}
                />
              </Box>
              <Typography variant="caption" fontWeight="bold" sx={{ minWidth: 40, textAlign: 'right' }}>
                {(trait.value * 100).toFixed(0)}%
              </Typography>
            </Box>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default function MLStyleProfile() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [summary, setSummary] = useState(null);
  const [expanded, setExpanded] = useState({
    traits: true,
    strengths: true,
    improvements: true,
    timing: false,
  });
  
  const fetchSummary = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchAPI('/api/ml/style/summary');
      if (data.success) {
        setSummary(data);
        setError(null);
      } else {
        setError(data.error || 'Failed to load style profile');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);
  
  const handleAnalyze = async () => {
    try {
      setAnalyzing(true);
      const data = await fetchAPI('/api/ml/style/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ min_trades: 5 }),
      });
      if (data.success) {
        await fetchSummary();
      } else {
        setError(data.error || 'Analysis failed');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };
  
  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);
  
  const profile = summary?.profile || {};
  const hasProfile = summary?.status === 'analyzed';
  const confidence = summary?.confidence || 0;
  
  // Format preferred hours for display
  const formatHours = (hours) => {
    if (!hours || hours.length === 0) return 'No data';
    return hours.map(h => `${h}:00`).join(', ');
  };
  
  const formatDays = (days) => {
    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    if (!days || days.length === 0) return 'No data';
    return days.map(d => dayNames[d] || d).join(', ');
  };
  
  return (
    <Card sx={{ mb: 2, bgcolor: 'background.paper' }}>
      <CardContent>
        {/* Header */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <Fingerprint color="secondary" />
            <Typography variant="h6">Trading Style Profile</Typography>
            {hasProfile && (
              <Tooltip title={`Confidence: ${(confidence * 100).toFixed(0)}%`}>
                <Chip
                  label={confidence > 0.7 ? 'High Confidence' : confidence > 0.4 ? 'Moderate' : 'Building...'}
                  color={confidence > 0.7 ? 'success' : confidence > 0.4 ? 'warning' : 'default'}
                  size="small"
                />
              </Tooltip>
            )}
          </Box>
          <Box display="flex" gap={1}>
            <Button
              variant="outlined"
              size="small"
              onClick={handleAnalyze}
              disabled={analyzing}
              startIcon={analyzing ? <CircularProgress size={16} /> : <Psychology />}
            >
              {analyzing ? 'Analyzing...' : 'Analyze Style'}
            </Button>
            <Tooltip title="Refresh">
              <IconButton onClick={fetchSummary} size="small">
                <Refresh />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        
        {loading ? (
          <Box display="flex" justifyContent="center" py={4}>
            <CircularProgress />
          </Box>
        ) : !hasProfile ? (
          <Alert severity="info" icon={<Psychology />}>
            <Typography variant="body2">
              {summary?.message || 'Need more trades to build your trading style profile.'}
              {summary?.trades_analyzed > 0 && ` (${summary.trades_analyzed} trades analyzed)`}
            </Typography>
            <Button
              variant="text"
              size="small"
              onClick={handleAnalyze}
              sx={{ mt: 1 }}
            >
              Try Analysis with Current Data
            </Button>
          </Alert>
        ) : (
          <>
            {/* Style Summary Cards */}
            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid item xs={6} sm={4}>
                <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: 'action.hover' }}>
                  <Typography variant="caption" color="text.secondary">Risk Profile</Typography>
                  <Typography variant="h6" fontWeight="bold" color={
                    profile.risk_appetite > 0.6 ? 'error.main' : 
                    profile.risk_appetite < 0.4 ? 'success.main' : 'warning.main'
                  }>
                    {profile.risk_appetite > 0.6 ? 'Aggressive' : 
                     profile.risk_appetite < 0.4 ? 'Conservative' : 'Moderate'}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6} sm={4}>
                <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: 'action.hover' }}>
                  <Typography variant="caption" color="text.secondary">Market Bias</Typography>
                  <Typography variant="h6" fontWeight="bold" color={
                    profile.trend_preference === 'bullish' ? 'success.main' : 
                    profile.trend_preference === 'bearish' ? 'error.main' : 'info.main'
                  }>
                    {(profile.trend_preference || 'Neutral').charAt(0).toUpperCase() + (profile.trend_preference || 'neutral').slice(1)}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6} sm={4}>
                <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: 'action.hover' }}>
                  <Typography variant="caption" color="text.secondary">Win Rate</Typography>
                  <Typography variant="h6" fontWeight="bold" color={
                    (profile.win_rate || 0) > 0.5 ? 'success.main' : 'error.main'
                  }>
                    {((profile.win_rate || 0) * 100).toFixed(1)}%
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6} sm={4}>
                <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: 'action.hover' }}>
                  <Typography variant="caption" color="text.secondary">Avg Hold</Typography>
                  <Typography variant="h6" fontWeight="bold">
                    {(profile.avg_hold_duration_hours || 0).toFixed(1)}h
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6} sm={4}>
                <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: 'action.hover' }}>
                  <Typography variant="caption" color="text.secondary">Profit Factor</Typography>
                  <Typography variant="h6" fontWeight="bold" color={
                    (profile.profit_factor || 0) > 1.5 ? 'success.main' : 
                    (profile.profit_factor || 0) < 1 ? 'error.main' : 'warning.main'
                  }>
                    {(profile.profit_factor || 0).toFixed(2)}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6} sm={4}>
                <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: 'action.hover' }}>
                  <Typography variant="caption" color="text.secondary">Style</Typography>
                  <Typography variant="h6" fontWeight="bold">
                    {(profile.scaling_behavior || 'All In').replace(/_/g, ' ').split(' ').map(
                      w => w.charAt(0).toUpperCase() + w.slice(1)
                    ).join(' ')}
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
            
            <Divider sx={{ my: 2 }} />
            
            {/* Trading DNA Visualization */}
            <Box mb={2}>
              <Box
                display="flex"
                alignItems="center"
                justifyContent="space-between"
                onClick={() => setExpanded(e => ({ ...e, traits: !e.traits }))}
                sx={{ cursor: 'pointer' }}
              >
                <Typography variant="subtitle1" fontWeight="bold">
                  <Fingerprint sx={{ fontSize: 18, mr: 1, verticalAlign: 'middle' }} />
                  Trading DNA
                </Typography>
                {expanded.traits ? <ExpandLess /> : <ExpandMore />}
              </Box>
              <Collapse in={expanded.traits}>
                <Paper sx={{ bgcolor: 'action.hover', mt: 1 }}>
                  <StyleRadar profile={profile} />
                </Paper>
              </Collapse>
            </Box>
            
            {/* Timing Preferences */}
            <Box mb={2}>
              <Box
                display="flex"
                alignItems="center"
                justifyContent="space-between"
                onClick={() => setExpanded(e => ({ ...e, timing: !e.timing }))}
                sx={{ cursor: 'pointer' }}
              >
                <Typography variant="subtitle1" fontWeight="bold">
                  <AccessTime sx={{ fontSize: 18, mr: 1, verticalAlign: 'middle' }} />
                  Timing Preferences
                </Typography>
                {expanded.timing ? <ExpandLess /> : <ExpandMore />}
              </Box>
              <Collapse in={expanded.timing}>
                <Paper sx={{ p: 2, bgcolor: 'action.hover', mt: 1 }}>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="caption" color="text.secondary">Best Trading Hours</Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {formatHours(profile.preferred_entry_hours)}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="caption" color="text.secondary">Most Active Days</Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {formatDays(profile.preferred_days)}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="caption" color="text.secondary">Patience Level</Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {profile.patience_factor > 0.6 ? 'Patient' : profile.patience_factor < 0.4 ? 'Reactive' : 'Moderate'}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="caption" color="text.secondary">Volatility Preference</Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {(profile.volatility_preference || 'Medium').charAt(0).toUpperCase() + (profile.volatility_preference || 'medium').slice(1)}
                      </Typography>
                    </Grid>
                  </Grid>
                </Paper>
              </Collapse>
            </Box>
            
            {/* Strengths */}
            {summary?.strengths && summary.strengths.length > 0 && (
              <Box mb={2}>
                <Box
                  display="flex"
                  alignItems="center"
                  justifyContent="space-between"
                  onClick={() => setExpanded(e => ({ ...e, strengths: !e.strengths }))}
                  sx={{ cursor: 'pointer' }}
                >
                  <Typography variant="subtitle1" fontWeight="bold">
                    <EmojiEvents sx={{ fontSize: 18, mr: 1, verticalAlign: 'middle', color: 'success.main' }} />
                    Strengths
                  </Typography>
                  {expanded.strengths ? <ExpandLess /> : <ExpandMore />}
                </Box>
                <Collapse in={expanded.strengths}>
                  <Box sx={{ mt: 1 }}>
                    {summary.strengths.map((strength, idx) => (
                      <Chip
                        key={idx}
                        icon={<CheckCircle />}
                        label={strength}
                        color="success"
                        variant="outlined"
                        size="small"
                        sx={{ m: 0.5 }}
                      />
                    ))}
                  </Box>
                </Collapse>
              </Box>
            )}
            
            {/* Areas to Improve */}
            {summary?.areas_to_improve && summary.areas_to_improve.length > 0 && (
              <Box mb={2}>
                <Box
                  display="flex"
                  alignItems="center"
                  justifyContent="space-between"
                  onClick={() => setExpanded(e => ({ ...e, improvements: !e.improvements }))}
                  sx={{ cursor: 'pointer' }}
                >
                  <Typography variant="subtitle1" fontWeight="bold">
                    <Warning sx={{ fontSize: 18, mr: 1, verticalAlign: 'middle', color: 'warning.main' }} />
                    Areas to Improve
                  </Typography>
                  {expanded.improvements ? <ExpandLess /> : <ExpandMore />}
                </Box>
                <Collapse in={expanded.improvements}>
                  <Box sx={{ mt: 1 }}>
                    {summary.areas_to_improve.map((area, idx) => (
                      <Alert
                        key={idx}
                        severity="warning"
                        icon={<Warning fontSize="small" />}
                        sx={{ mb: 1, py: 0 }}
                      >
                        <Typography variant="body2">{area}</Typography>
                      </Alert>
                    ))}
                  </Box>
                </Collapse>
              </Box>
            )}
            
            {/* Metadata */}
            <Typography variant="caption" color="text.secondary" display="block" textAlign="right">
              Based on {profile.total_trades_analyzed || 0} trades • 
              Analyzed: {profile.analysis_date ? new Date(profile.analysis_date).toLocaleDateString() : 'Never'}
            </Typography>
          </>
        )}
      </CardContent>
    </Card>
  );
}
