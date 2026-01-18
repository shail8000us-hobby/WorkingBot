/**
 * Comprehensive Bot Brain Dashboard
 * 
 * The ultimate real-time bot monitoring interface that shows:
 * - What the bot is thinking right now
 * - What it will do next with confidence scores
 * - File changes and their impact
 * - Market conditions and risk factors
 * - Alternative scenarios and predictions
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  Chip,
  Alert,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Badge,
  Tooltip,
  IconButton
} from '@mui/material';
import {
  Psychology,
  Visibility,
  TrendingUp,
  Warning,
  CheckCircle,
  Error,
  Schedule,
  MonetizationOn,
  Speed,
  Security,
  FilePresent,
  Refresh,
  ExpandMore,
  NotificationImportant
} from '@mui/icons-material';

const ComprehensiveDashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchData = async () => {
    try {
      setError(null);
      const response = await fetch('/api/brain/predict');
      const result = await response.json();
      
      if (result.success) {
        setData(result);
        setLastUpdate(new Date());
      } else {
        setError(result.error || 'Failed to load brain data');
      }
    } catch (err) {
      console.error('Error fetching brain data:', err);
      setError('Failed to connect to brain analyzer API');
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh every 3 seconds
  useEffect(() => {
    fetchData();
    let interval;
    if (autoRefresh) {
      interval = setInterval(fetchData, 30000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return '#4caf50';
    if (confidence >= 0.6) return '#ff9800';
    return '#f44336';
  };

  const getImpactColor = (level) => {
    switch (level) {
      case 'critical': return '#f44336';
      case 'high': return '#ff5722';
      case 'medium': return '#ff9800';
      case 'low': return '#4caf50';
      default: return '#9e9e9e';
    }
  };

  if (loading && !data) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center' }}>
        <LinearProgress sx={{ mb: 2 }} />
        <Typography>Analyzing bot brain in real-time...</Typography>
      </Paper>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!data) {
    return (
      <Alert severity="info" sx={{ mt: 2 }}>
        No brain data available
      </Alert>
    );
  }

  const {
    predictions = {},
    file_changes = [],
    monitoring = {}
  } = data;

  const {
    primary_prediction = {},
    market_analysis = {},
    confidence_metrics = {},
    risk_factors = [],
    monitoring_alerts = []
  } = predictions;

  const criticalChanges = file_changes.filter(c => c.impact_level === 'critical').length;
  const totalAlerts = monitoring_alerts.length + (monitoring.alerts || []).length;

  return (
    <Box sx={{ mt: 2 }}>
      {/* Header with live status and controls */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
          🧠 Bot Brain Monitor
          <Chip 
            label="LIVE" 
            size="small" 
            sx={{ 
              bgcolor: '#4caf50', 
              color: '#fff', 
              animation: autoRefresh ? 'pulse 2s infinite' : 'none'
            }}
          />
          {criticalChanges > 0 && (
            <Badge badgeContent={criticalChanges} color="error">
              <NotificationImportant sx={{ color: '#f44336' }} />
            </Badge>
          )}
        </Typography>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {lastUpdate && (
            <Typography variant="caption" color="text.secondary">
              Last update: {lastUpdate.toLocaleTimeString()}
            </Typography>
          )}
          <Tooltip title={autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}>
            <IconButton 
              onClick={() => setAutoRefresh(!autoRefresh)}
              color={autoRefresh ? 'success' : 'default'}
            >
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Critical Alerts Banner */}
      {(criticalChanges > 0 || totalAlerts > 0) && (
        <Alert 
          severity="warning" 
          sx={{ mb: 3, fontWeight: 'bold' }}
          icon={<NotificationImportant />}
        >
          {criticalChanges > 0 && `${criticalChanges} critical file changes detected! `}
          {totalAlerts > 0 && `${totalAlerts} active monitoring alerts.`}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Current Bot State - Large Card */}
        <Grid item xs={12}>
          <Card elevation={3} sx={{ bgcolor: '#1a1a1a', border: '2px solid #4caf50' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
                <Psychology sx={{ fontSize: 40, color: '#4caf50' }} />
                <Box sx={{ flex: 1 }}>
                  <Typography variant="h5" sx={{ fontWeight: 'bold', color: '#4caf50' }}>
                    Bot's Current Thinking
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Real-time analysis of decision-making process
                  </Typography>
                </Box>
                <Chip 
                  label={`${(primary_prediction?.confidence * 100 || 0).toFixed(0)}% Confidence`}
                  sx={{ 
                    bgcolor: getConfidenceColor(primary_prediction?.confidence || 0),
                    color: '#fff',
                    fontWeight: 'bold',
                    fontSize: '1rem',
                    height: 32
                  }}
                />
              </Box>
              
              <Typography variant="h6" sx={{ mb: 2, color: '#fff', fontSize: '1.3rem' }}>
                Next Action: {primary_prediction?.action || 'Analyzing...'}
              </Typography>
              
              <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                {primary_prediction?.reasoning || 'No reasoning available'}
              </Typography>
              
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {primary_prediction?.estimated_time && (
                  <Chip 
                    icon={<Schedule />}
                    label={`ETA: ${primary_prediction.estimated_time}`}
                    size="medium"
                    variant="outlined"
                    sx={{ color: '#fff' }}
                  />
                )}
                {primary_prediction?.price_trigger && (
                  <Chip 
                    icon={<MonetizationOn />}
                    label={`Trigger: ₹${primary_prediction.price_trigger.toLocaleString()}`}
                    size="medium"
                    variant="outlined"
                    sx={{ color: '#fff' }}
                  />
                )}
                {market_analysis?.trading_safe !== undefined && (
                  <Chip 
                    icon={market_analysis.trading_safe ? <CheckCircle /> : <Warning />}
                    label={market_analysis.trading_safe ? 'Trading Active' : 'Trading Halted'}
                    size="medium"
                    color={market_analysis.trading_safe ? 'success' : 'error'}
                  />
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Market Conditions */}
        <Grid item xs={12} md={4}>
          <Card elevation={2}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                📊 Market Conditions
                <Chip 
                  label={market_analysis?.condition || 'Unknown'}
                  size="small"
                  color={market_analysis?.trading_safe ? 'success' : 'error'}
                />
              </Typography>
              
              {market_analysis?.iv_percentage !== undefined && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2">
                    Implied Volatility: {market_analysis.iv_percentage.toFixed(1)}%
                  </Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={Math.min(market_analysis.iv_percentage, 100)}
                    color={market_analysis.iv_percentage > 80 ? 'error' : 'success'}
                    sx={{ height: 6, borderRadius: 3 }}
                  />
                </Box>
              )}
              
              {market_analysis?.position_utilization !== undefined && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2">
                    Position Usage: {market_analysis.position_utilization.toFixed(1)}%
                  </Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={market_analysis.position_utilization}
                    color={market_analysis.position_utilization > 80 ? 'warning' : 'success'}
                    sx={{ height: 6, borderRadius: 3 }}
                  />
                </Box>
              )}
              
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip 
                  label={market_analysis?.risk_level || 'Unknown'}
                  size="small"
                  color={market_analysis?.risk_level === 'low' ? 'success' : 
                         market_analysis?.risk_level === 'medium' ? 'warning' : 'error'}
                />
                <Chip 
                  label={market_analysis?.volatility_level || 'Unknown'}
                  size="small"
                  variant="outlined"
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* File Changes Monitor */}
        <Grid item xs={12} md={4}>
          <Card elevation={2}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                📁 File Changes
                {file_changes.length > 0 && (
                  <Badge badgeContent={file_changes.length} color="warning">
                    <FilePresent />
                  </Badge>
                )}
              </Typography>
              
              {file_changes.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No recent file changes detected
                </Typography>
              ) : (
                <List dense>
                  {file_changes.slice(0, 3).map((change, index) => (
                    <ListItem key={index} sx={{ px: 0 }}>
                      <ListItemIcon>
                        <FilePresent sx={{ color: getImpactColor(change.impact_level) }} />
                      </ListItemIcon>
                      <ListItemText 
                        primary={change.file_path}
                        secondary={
                          <Box>
                            <Typography variant="caption" display="block">
                              {change.change_type.toUpperCase()} - {change.impact_level} impact
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {change.predicted_impact}
                            </Typography>
                          </Box>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              )}
              
              {monitoring?.monitoring_state && (
                <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                  <Typography variant="caption" color="text.secondary">
                    Monitoring {monitoring.monitoring_state.files_watched} files
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* System Health */}
        <Grid item xs={12} md={4}>
          <Card elevation={2}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                🏥 System Health
              </Typography>
              
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2">
                  Prediction Quality: {confidence_metrics?.prediction_quality || 'Unknown'}
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={(confidence_metrics?.overall_confidence || 0) * 100}
                  color={confidence_metrics?.prediction_quality === 'high' ? 'success' : 
                         confidence_metrics?.prediction_quality === 'medium' ? 'warning' : 'error'}
                  sx={{ height: 6, borderRadius: 3 }}
                />
              </Box>
              
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                <Chip 
                  label={`${confidence_metrics?.scenario_count || 0} scenarios`}
                  size="small"
                  variant="outlined"
                />
                <Chip 
                  label={`${risk_factors?.length || 0} risks`}
                  size="small"
                  color={risk_factors?.length > 0 ? 'warning' : 'success'}
                />
              </Box>
              
              {monitoring_alerts?.length > 0 && (
                <Alert severity="info" sx={{ mt: 1 }}>
                  {monitoring_alerts.length} active monitoring alert{monitoring_alerts.length > 1 ? 's' : ''}
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Risk Factors */}
        {risk_factors?.length > 0 && (
          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" gutterBottom sx={{ color: '#f44336' }}>
                  ⚠️ Active Risk Factors
                </Typography>
                
                <List dense>
                  {risk_factors.map((risk, index) => (
                    <ListItem key={index} sx={{ px: 0 }}>
                      <ListItemIcon>
                        <Warning sx={{ 
                          color: risk.severity === 'high' ? '#f44336' : 
                                 risk.severity === 'medium' ? '#ff9800' : '#ffeb3b'
                        }} />
                      </ListItemIcon>
                      <ListItemText 
                        primary={risk.description}
                        secondary={`Impact: ${risk.impact} | Severity: ${risk.severity}`}
                      />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Monitoring Alerts */}
        {monitoring_alerts?.length > 0 && (
          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  🔔 Active Monitoring
                </Typography>
                
                <List dense>
                  {monitoring_alerts.map((alert, index) => (
                    <ListItem key={index} sx={{ px: 0 }}>
                      <ListItemIcon>
                        <Speed sx={{ 
                          color: alert.urgency === 'high' ? '#f44336' : 
                                 alert.urgency === 'medium' ? '#ff9800' : '#4caf50'
                        }} />
                      </ListItemIcon>
                      <ListItemText 
                        primary={alert.message}
                        secondary={`Priority: ${alert.urgency}`}
                      />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Alternative Scenarios */}
        {predictions?.alternative_scenarios?.length > 0 && (
          <Grid item xs={12}>
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="h6">
                  🎯 Alternative Scenarios ({predictions.alternative_scenarios.length})
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Grid container spacing={2}>
                  {predictions.alternative_scenarios.map((scenario, index) => (
                    <Grid item xs={12} md={6} lg={4} key={index}>
                      <Card variant="outlined" sx={{ height: '100%' }}>
                        <CardContent>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                              {scenario.condition?.replace('_', ' ').toUpperCase()}
                            </Typography>
                            <Chip 
                              label={`${(scenario.confidence * 100).toFixed(0)}%`}
                              size="small"
                              sx={{ bgcolor: getConfidenceColor(scenario.confidence), color: '#fff' }}
                            />
                          </Box>
                          
                          <Typography variant="body2" sx={{ mb: 1 }}>
                            {scenario.next_action}
                          </Typography>
                          
                          <Typography variant="caption" color="text.secondary">
                            {scenario.reasoning}
                          </Typography>
                          
                          {scenario.price_trigger && (
                            <Chip 
                              label={`₹${scenario.price_trigger.toLocaleString()}`}
                              size="small"
                              variant="outlined"
                              sx={{ mt: 1 }}
                            />
                          )}
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              </AccordionDetails>
            </Accordion>
          </Grid>
        )}
      </Grid>

      {/* CSS for animations */}
      <style jsx>{`
        @keyframes pulse {
          0% { opacity: 1; }
          50% { opacity: 0.5; }
          100% { opacity: 1; }
        }
      `}</style>
    </Box>
  );
};

export default ComprehensiveDashboard;