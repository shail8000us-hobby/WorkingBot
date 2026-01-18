/**
 * ML Trading Insights Panel
 * 
 * Shows machine learning insights from trade history:
 * - Trade statistics
 * - Pattern analysis
 * - Automation rule suggestions
 * - Model training status
 * 
 * Created: January 14, 2026
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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  Psychology as MLIcon,
  TrendingUp,
  TrendingDown,
  CheckCircle,
  Lightbulb,
  Refresh,
  ExpandMore,
  ExpandLess,
  AutoMode,
  School,
  Analytics,
  Timeline,
} from '@mui/icons-material';

// Simple fetch without api shim to debug
const fetchAPI = async (url) => {
  const response = await fetch(url);
  return response.json();
};

export default function MLInsightsPanel() {
  console.log('MLInsightsPanel: Component mounting');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dashboard, setDashboard] = useState({
    statistics: { total_trades: 0, win_rate: 0, total_pnl: 0 },
    model: { is_trained: false, can_train: false },
    readiness: { trades_needed: 30 },
  });
  const [training, setTraining] = useState(false);
  const [expanded, setExpanded] = useState({
    stats: true,
    patterns: false,
    rules: true,
    features: false,
  });
  const [tradesDialogOpen, setTradesDialogOpen] = useState(false);
  const [recentTrades, setRecentTrades] = useState([]);
  
  const fetchDashboard = useCallback(async () => {
    console.log('MLInsightsPanel: Fetching dashboard...');
    try {
      setLoading(true);
      const data = await fetchAPI('/api/ml/dashboard');
      console.log('MLInsightsPanel: Got response:', data);
      if (data.success) {
        setDashboard(data);
        setError(null);
      } else {
        setError(data.error || 'Failed to load ML dashboard');
      }
    } catch (err) {
      console.error('MLInsightsPanel: Fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);
  
  const handleTrain = async () => {
    try {
      setTraining(true);
      const data = await fetchAPI('/api/ml/model/train');
      if (data.success) {
        await fetchDashboard();
      } else {
        setError(data.error || 'Training failed');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setTraining(false);
    }
  };
  
  const fetchTrades = async () => {
    try {
      const data = await fetchAPI('/api/ml/trades?days=30');
      if (data.success) {
        setRecentTrades(data.trades || []);
      }
    } catch (err) {
      console.error('Failed to fetch trades:', err);
    }
  };
  
  useEffect(() => {
    console.log('MLInsightsPanel: useEffect running');
    fetchDashboard();
  }, [fetchDashboard]);
  
  // Always show the panel, even during loading
  const stats = dashboard?.statistics || {};
  const patterns = dashboard?.patterns || {};
  const rules = dashboard?.automation_rules || [];
  const readiness = dashboard?.readiness || {};
  const model = dashboard?.model || {};
  
  const winRate = stats.win_rate || 0;
  const totalPnl = stats.total_pnl || 0;
  
  return (
    <Card sx={{ mb: 2, bgcolor: 'background.paper' }}>
      <CardContent>
        {/* Header */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <MLIcon color="primary" />
            <Typography variant="h6">ML Trading Insights</Typography>
            {model.is_trained && (
              <Tooltip title={`Accuracy: ${((model.metadata?.metrics?.accuracy || 0) * 100).toFixed(1)}%`}>
                <Chip 
                  label="Model Trained" 
                  color="success" 
                  size="small" 
                  icon={<CheckCircle />}
                />
              </Tooltip>
            )}
          </Box>
          <Box display="flex" gap={1}>
            <Tooltip title="View recent trades">
              <IconButton 
                onClick={() => { fetchTrades(); setTradesDialogOpen(true); }}
                size="small"
              >
                <Timeline />
              </IconButton>
            </Tooltip>
            <Tooltip title="Refresh">
              <IconButton onClick={fetchDashboard} size="small">
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
        
        {/* Model Performance Metrics (when trained) */}
        {model.is_trained && model.metadata && (
          <Paper sx={{ p: 2, mb: 2, bgcolor: 'success.dark', opacity: 0.95 }}>
            <Typography variant="subtitle2" gutterBottom sx={{ color: 'white', display: 'flex', alignItems: 'center', gap: 1 }}>
              <CheckCircle sx={{ fontSize: 18 }} />
              Model Performance Metrics
            </Typography>
            <Grid container spacing={2} sx={{ mt: 0.5 }}>
              <Grid item xs={6} sm={3}>
                <Box textAlign="center">
                  <Typography variant="h5" fontWeight="bold" sx={{ color: 'white' }}>
                    {((model.metadata.metrics?.accuracy || 0) * 100).toFixed(1)}%
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.8)' }}>
                    Accuracy
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box textAlign="center">
                  <Typography variant="h5" fontWeight="bold" sx={{ color: 'white' }}>
                    {((model.metadata.metrics?.precision || 0) * 100).toFixed(1)}%
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.8)' }}>
                    Precision
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box textAlign="center">
                  <Typography variant="h5" fontWeight="bold" sx={{ color: 'white' }}>
                    {((model.metadata.metrics?.recall || 0) * 100).toFixed(1)}%
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.8)' }}>
                    Recall
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box textAlign="center">
                  <Typography variant="h5" fontWeight="bold" sx={{ color: 'white' }}>
                    {((model.metadata.metrics?.f1_score || 0) * 100).toFixed(1)}%
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.8)' }}>
                    F1 Score
                  </Typography>
                </Box>
              </Grid>
            </Grid>
            {model.metadata.trained_at && (
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', display: 'block', mt: 1, textAlign: 'right' }}>
                Trained: {new Date(model.metadata.trained_at).toLocaleString()} • 
                {model.metadata.num_trades} trades used
              </Typography>
            )}
          </Paper>
        )}
        
        {/* Feature Importance Section (when trained) */}
        {model.is_trained && model.metadata?.feature_importance && (
          <Box mb={2}>
            <Box 
              display="flex" 
              alignItems="center" 
              justifyContent="space-between"
              onClick={() => setExpanded(e => ({ ...e, features: !e.features }))}
              sx={{ cursor: 'pointer' }}
            >
              <Typography variant="subtitle1" fontWeight="bold">
                <TrendingUp sx={{ fontSize: 18, mr: 1, verticalAlign: 'middle' }} />
                Feature Importance
              </Typography>
              {expanded.features ? <ExpandLess /> : <ExpandMore />}
            </Box>
            <Collapse in={expanded.features}>
              <Paper sx={{ p: 2, mt: 1, bgcolor: 'action.hover' }}>
                {Object.entries(model.metadata.feature_importance)
                  .filter(([_, val]) => val > 0)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 6)
                  .map(([feature, importance]) => (
                    <Box key={feature} mb={1}>
                      <Box display="flex" justifyContent="space-between" mb={0.5}>
                        <Typography variant="caption" sx={{ textTransform: 'capitalize' }}>
                          {feature.replace(/_/g, ' ')}
                        </Typography>
                        <Typography variant="caption" fontWeight="bold">
                          {(importance * 100).toFixed(1)}%
                        </Typography>
                      </Box>
                      <LinearProgress 
                        variant="determinate" 
                        value={importance * 100}
                        sx={{ 
                          height: 6, 
                          borderRadius: 1,
                          bgcolor: 'action.selected',
                          '& .MuiLinearProgress-bar': {
                            bgcolor: importance > 0.5 ? 'success.main' : importance > 0.2 ? 'warning.main' : 'info.main'
                          }
                        }}
                      />
                    </Box>
                  ))}
                {Object.values(model.metadata.feature_importance).filter(v => v > 0).length === 0 && (
                  <Typography variant="body2" color="text.secondary">
                    Feature importance will be calculated after more diverse training data.
                  </Typography>
                )}
              </Paper>
            </Collapse>
          </Box>
        )}
        
        {/* Readiness Progress */}
        {!model.is_trained && (
          <Paper sx={{ p: 2, mb: 2, bgcolor: 'action.hover' }}>
            <Typography variant="subtitle2" gutterBottom>
              <School sx={{ fontSize: 18, mr: 1, verticalAlign: 'middle' }} />
              ML Training Progress
            </Typography>
            <Box mb={1}>
              <Box display="flex" justifyContent="space-between" mb={0.5}>
                <Typography variant="caption">
                  Trades: {stats.total_trades || 0} / 30 needed
                </Typography>
                <Typography variant="caption">
                  {Math.min(100, ((stats.total_trades || 0) / 30) * 100).toFixed(0)}%
                </Typography>
              </Box>
              <LinearProgress 
                variant="determinate" 
                value={Math.min(100, ((stats.total_trades || 0) / 30) * 100)}
                sx={{ height: 8, borderRadius: 1 }}
              />
            </Box>
            <Box mb={1}>
              <Box display="flex" justifyContent="space-between" mb={0.5}>
                <Typography variant="caption">
                  Closed Trades: {stats.closed_trades || 0} / 20 needed
                </Typography>
                <Typography variant="caption">
                  {Math.min(100, ((stats.closed_trades || 0) / 20) * 100).toFixed(0)}%
                </Typography>
              </Box>
              <LinearProgress 
                variant="determinate" 
                value={Math.min(100, ((stats.closed_trades || 0) / 20) * 100)}
                color="secondary"
                sx={{ height: 8, borderRadius: 1 }}
              />
            </Box>
            {readiness.can_train && (
              <Button
                variant="contained"
                color="primary"
                onClick={handleTrain}
                disabled={training}
                startIcon={training ? <CircularProgress size={16} /> : <School />}
                sx={{ mt: 1 }}
              >
                {training ? 'Training...' : 'Train ML Model'}
              </Button>
            )}
            {!readiness.can_train && (
              <Typography variant="caption" color="text.secondary">
                Keep trading! Need {readiness.trades_needed || 0} more trades and{' '}
                {readiness.closed_trades_needed || 0} more closed trades to train the model.
              </Typography>
            )}
          </Paper>
        )}
        
        {/* Statistics Section */}
        <Box mb={2}>
          <Box 
            display="flex" 
            alignItems="center" 
            justifyContent="space-between"
            onClick={() => setExpanded(e => ({ ...e, stats: !e.stats }))}
            sx={{ cursor: 'pointer' }}
          >
            <Typography variant="subtitle1" fontWeight="bold">
              <Analytics sx={{ fontSize: 18, mr: 1, verticalAlign: 'middle' }} />
              Trade Statistics
            </Typography>
            {expanded.stats ? <ExpandLess /> : <ExpandMore />}
          </Box>
          <Collapse in={expanded.stats}>
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <Grid item xs={6} sm={3}>
                <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: 'action.hover' }}>
                  <Typography variant="h4" fontWeight="bold" color="primary">
                    {stats.total_trades || 0}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Total Trades
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: 'action.hover' }}>
                  <Typography 
                    variant="h4" 
                    fontWeight="bold" 
                    color={winRate >= 50 ? 'success.main' : 'error.main'}
                  >
                    {winRate.toFixed(1)}%
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Win Rate{stats.closed_trades === 0 && ' (needs closed trades)'}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: 'action.hover' }}>
                  <Typography 
                    variant="h4" 
                    fontWeight="bold"
                    color={totalPnl >= 0 ? 'success.main' : 'error.main'}
                  >
                    ${totalPnl.toFixed(0)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {stats.unrealized ? 'Unrealized' : 'Total'} PnL
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Paper sx={{ p: 1.5, textAlign: 'center', bgcolor: 'action.hover' }}>
                  <Typography variant="h4" fontWeight="bold" color="info.main">
                    {stats.open_trades || 0}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Open Trades
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
          </Collapse>
        </Box>
        
        <Divider sx={{ my: 2 }} />
        
        {/* Pattern Analysis */}
        {patterns && Object.keys(patterns).length > 0 && (
          <Box mb={2}>
            <Box 
              display="flex" 
              alignItems="center" 
              justifyContent="space-between"
              onClick={() => setExpanded(e => ({ ...e, patterns: !e.patterns }))}
              sx={{ cursor: 'pointer' }}
            >
              <Typography variant="subtitle1" fontWeight="bold">
                <Lightbulb sx={{ fontSize: 18, mr: 1, verticalAlign: 'middle' }} />
                Pattern Analysis
              </Typography>
              {expanded.patterns ? <ExpandLess /> : <ExpandMore />}
            </Box>
            <Collapse in={expanded.patterns}>
              <Grid container spacing={2} sx={{ mt: 1 }}>
                {/* Option Type Performance */}
                {patterns.call_win_rate !== undefined && (
                  <Grid item xs={12} sm={6}>
                    <Paper sx={{ p: 2, bgcolor: 'action.hover' }}>
                      <Typography variant="subtitle2" gutterBottom>Option Type Performance</Typography>
                      <Box display="flex" justifyContent="space-around">
                        <Box textAlign="center">
                          <Typography variant="h5" color={patterns.call_win_rate > 0.5 ? 'success.main' : 'error.main'}>
                            {(patterns.call_win_rate * 100).toFixed(0)}%
                          </Typography>
                          <Typography variant="caption">Calls</Typography>
                        </Box>
                        <Box textAlign="center">
                          <Typography variant="h5" color={patterns.put_win_rate > 0.5 ? 'success.main' : 'error.main'}>
                            {(patterns.put_win_rate * 100).toFixed(0)}%
                          </Typography>
                          <Typography variant="caption">Puts</Typography>
                        </Box>
                      </Box>
                    </Paper>
                  </Grid>
                )}
                
                {/* Market Trend Performance */}
                {patterns.trend_performance && (
                  <Grid item xs={12} sm={6}>
                    <Paper sx={{ p: 2, bgcolor: 'action.hover' }}>
                      <Typography variant="subtitle2" gutterBottom>Market Trend Performance</Typography>
                      <Box display="flex" justifyContent="space-around">
                        {Object.entries(patterns.trend_performance).map(([trend, wr]) => (
                          <Box key={trend} textAlign="center">
                            <Typography 
                              variant="h5" 
                              color={wr > 0.5 ? 'success.main' : wr < 0.4 ? 'error.main' : 'warning.main'}
                            >
                              {(wr * 100).toFixed(0)}%
                            </Typography>
                            <Typography variant="caption" sx={{ textTransform: 'capitalize' }}>
                              {trend}
                            </Typography>
                          </Box>
                        ))}
                      </Box>
                    </Paper>
                  </Grid>
                )}
              </Grid>
            </Collapse>
          </Box>
        )}
        
        {/* Automation Rules */}
        {rules && rules.length > 0 && (
          <Box>
            <Box 
              display="flex" 
              alignItems="center" 
              justifyContent="space-between"
              onClick={() => setExpanded(e => ({ ...e, rules: !e.rules }))}
              sx={{ cursor: 'pointer' }}
            >
              <Typography variant="subtitle1" fontWeight="bold">
                <AutoMode sx={{ fontSize: 18, mr: 1, verticalAlign: 'middle' }} />
                Automation Suggestions ({rules.length})
              </Typography>
              {expanded.rules ? <ExpandLess /> : <ExpandMore />}
            </Box>
            <Collapse in={expanded.rules}>
              <Box sx={{ mt: 1 }}>
                {rules.map((rule, idx) => (
                  <Paper 
                    key={rule.rule_id || idx}
                    sx={{ 
                      p: 2, 
                      mb: 1, 
                      bgcolor: rule.action === 'AVOID_ENTRY' ? 'error.dark' + '10' : 'success.dark' + '10',
                      borderLeft: `4px solid ${rule.action === 'AVOID_ENTRY' ? '#ef4444' : '#10b981'}`,
                    }}
                  >
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                      <Box>
                        <Typography variant="subtitle2" fontWeight="bold">
                          {rule.name}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {rule.description}
                        </Typography>
                      </Box>
                      <Chip 
                        label={rule.improvement}
                        size="small"
                        color={rule.action === 'AVOID_ENTRY' ? 'error' : 'success'}
                        sx={{ fontWeight: 'bold' }}
                      />
                    </Box>
                    <Box display="flex" gap={1} mt={1}>
                      <Chip 
                        label={rule.confidence} 
                        size="small" 
                        variant="outlined"
                        color={rule.confidence === 'high' ? 'success' : 'warning'}
                      />
                      <Chip 
                        label={rule.action.replace('_', ' ')} 
                        size="small" 
                        variant="outlined"
                      />
                    </Box>
                  </Paper>
                ))}
              </Box>
            </Collapse>
          </Box>
        )}
        
        {/* No Data State */}
        {!patterns && (!rules || rules.length === 0) && (
          <Alert severity="info" icon={<Lightbulb />}>
            <Typography variant="body2">
              Keep trading to unlock ML insights! The system learns from your trading patterns
              and will suggest optimizations after analyzing enough trades.
            </Typography>
          </Alert>
        )}
        
        {/* Recent Trades Dialog */}
        <Dialog 
          open={tradesDialogOpen} 
          onClose={() => setTradesDialogOpen(false)}
          maxWidth="md"
          fullWidth
        >
          <DialogTitle>
            Recent Trades (Last 30 Days)
          </DialogTitle>
          <DialogContent>
            {recentTrades.length === 0 ? (
              <Alert severity="info">No trades recorded yet</Alert>
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Date</TableCell>
                      <TableCell>Symbol</TableCell>
                      <TableCell>Action</TableCell>
                      <TableCell align="right">Qty</TableCell>
                      <TableCell align="right">Price</TableCell>
                      <TableCell align="right">PnL</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {recentTrades.slice(0, 50).map((trade, idx) => (
                      <TableRow key={trade.trade_id || idx}>
                        <TableCell>
                          {new Date(trade.timestamp).toLocaleDateString()}
                        </TableCell>
                        <TableCell>
                          <Chip 
                            label={`${trade.option_type === 'Call' ? 'C' : 'P'} ${trade.strike}`}
                            size="small"
                            color={trade.option_type === 'Call' ? 'success' : 'error'}
                            variant="outlined"
                          />
                        </TableCell>
                        <TableCell>
                          <Chip 
                            label={trade.action}
                            size="small"
                            color={trade.action === 'BUY' ? 'success' : 'error'}
                          />
                        </TableCell>
                        <TableCell align="right">{trade.quantity}</TableCell>
                        <TableCell align="right">${parseFloat(trade.price || 0).toFixed(2)}</TableCell>
                        <TableCell align="right">
                          {trade.outcome_pnl ? (
                            <Typography 
                              color={parseFloat(trade.outcome_pnl) >= 0 ? 'success.main' : 'error.main'}
                            >
                              ${parseFloat(trade.outcome_pnl).toFixed(2)}
                            </Typography>
                          ) : '-'}
                        </TableCell>
                        <TableCell>
                          <Chip 
                            label={trade.outcome_status || 'open'}
                            size="small"
                            variant="outlined"
                            color={trade.outcome_status === 'closed' ? 'default' : 'warning'}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setTradesDialogOpen(false)}>Close</Button>
          </DialogActions>
        </Dialog>
      </CardContent>
    </Card>
  );
}
