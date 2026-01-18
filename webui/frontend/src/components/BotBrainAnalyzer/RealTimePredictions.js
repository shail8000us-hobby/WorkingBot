/**
 * Real-Time Bot Predictions Component
 * 
 * Shows what the bot will do next with confidence scores and alternative scenarios.
 * Updates every 3 seconds for true real-time analysis.
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  LinearProgress,
  Alert,
  Card,
  CardContent,
  Grid,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Accordion,
  AccordionSummary,
  AccordionDetails
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Warning,
  CheckCircle,
  Schedule,
  Psychology,
  ExpandMore,
  MonetizationOn,
  Speed,
  Security
} from '@mui/icons-material';

const RealTimePredictions = () => {
  const [predictions, setPredictions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchPredictions = async () => {
    try {
      setError(null);
      const response = await fetch('/api/brain/predict');
      const data = await response.json();
      
      if (data.success) {
        setPredictions(data.predictions);
        setLastUpdate(new Date());
      } else {
        setError(data.error || 'Failed to load predictions');
      }
    } catch (err) {
      console.error('Error fetching predictions:', err);
      setError('Failed to connect to prediction API');
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh every 3 seconds
  useEffect(() => {
    fetchPredictions();
    const interval = setInterval(fetchPredictions, 30000);
    return () => clearInterval(interval);
  }, []);

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return '#4caf50'; // Green
    if (confidence >= 0.6) return '#ff9800'; // Orange
    return '#f44336'; // Red
  };

  const getMarketConditionIcon = (condition) => {
    switch (condition) {
      case 'normal': return <CheckCircle sx={{ color: '#4caf50' }} />;
      case 'high_volatility': return <Warning sx={{ color: '#f44336' }} />;
      case 'emergency': return <Security sx={{ color: '#f44336' }} />;
      case 'position_limit': return <MonetizationOn sx={{ color: '#ff9800' }} />;
      default: return <Psychology sx={{ color: '#9c27b0' }} />;
    }
  };

  if (loading && !predictions) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center' }}>
        <LinearProgress sx={{ mb: 2 }} />
        <Typography>Analyzing bot brain and market conditions...</Typography>
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

  if (!predictions) {
    return (
      <Alert severity="info" sx={{ mt: 2 }}>
        No prediction data available
      </Alert>
    );
  }

  const {
    primary_prediction,
    alternative_scenarios = [],
    confidence_metrics = {},
    market_analysis = {},
    next_decision_point = {},
    risk_factors = [],
    monitoring_alerts = []
  } = predictions;

  return (
    <Box sx={{ mt: 2 }}>
      {/* Header with live status */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
          🔮 Real-Time Bot Predictions
          <Chip 
            label="LIVE" 
            size="small" 
            sx={{ bgcolor: '#4caf50', color: '#fff', animation: 'pulse 2s infinite' }}
          />
        </Typography>
        {lastUpdate && (
          <Typography variant="caption" color="text.secondary">
            Last update: {lastUpdate.toLocaleTimeString()}
          </Typography>
        )}
      </Box>

      <Grid container spacing={3}>
        {/* Primary Prediction */}
        <Grid item xs={12} md={8}>
          <Card elevation={3} sx={{ bgcolor: '#1a1a1a', border: '2px solid #4caf50' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Psychology sx={{ fontSize: 32, color: '#4caf50' }} />
                <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#4caf50' }}>
                  Next Predicted Action
                </Typography>
                <Chip 
                  label={`${(primary_prediction?.confidence * 100 || 0).toFixed(0)}% Confidence`}
                  sx={{ 
                    bgcolor: getConfidenceColor(primary_prediction?.confidence || 0),
                    color: '#fff',
                    fontWeight: 'bold'
                  }}
                />
              </Box>
              
              <Typography variant="h6" sx={{ mb: 2, color: '#fff' }}>
                {primary_prediction?.action || 'No prediction available'}
              </Typography>
              
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {primary_prediction?.reasoning || 'No reasoning available'}
              </Typography>
              
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {primary_prediction?.estimated_time && (
                  <Chip 
                    icon={<Schedule />}
                    label={primary_prediction.estimated_time}
                    size="small"
                    variant="outlined"
                  />
                )}
                {primary_prediction?.price_trigger && (
                  <Chip 
                    icon={<MonetizationOn />}
                    label={`₹${primary_prediction.price_trigger.toLocaleString()}`}
                    size="small"
                    variant="outlined"
                  />
                )}
                {primary_prediction?.condition && (
                  <Chip 
                    icon={getMarketConditionIcon(primary_prediction.condition)}
                    label={primary_prediction.condition.replace('_', ' ').toUpperCase()}
                    size="small"
                    variant="outlined"
                  />
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Confidence Metrics */}
        <Grid item xs={12} md={4}>
          <Card elevation={2}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                📊 Prediction Quality
              </Typography>
              
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Overall Confidence
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={(confidence_metrics.overall_confidence || 0) * 100}
                  sx={{ 
                    height: 8, 
                    borderRadius: 4,
                    bgcolor: 'rgba(255,255,255,0.1)',
                    '& .MuiLinearProgress-bar': {
                      bgcolor: getConfidenceColor(confidence_metrics.overall_confidence || 0)
                    }
                  }}
                />
                <Typography variant="caption">
                  {((confidence_metrics.overall_confidence || 0) * 100).toFixed(1)}%
                </Typography>
              </Box>
              
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip 
                  label={confidence_metrics.prediction_quality || 'Unknown'}
                  size="small"
                  color={confidence_metrics.prediction_quality === 'high' ? 'success' : 
                         confidence_metrics.prediction_quality === 'medium' ? 'warning' : 'error'}
                />
                <Chip 
                  label={`${confidence_metrics.scenario_count || 0} scenarios`}
                  size="small"
                  variant="outlined"
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Market Analysis */}
        <Grid item xs={12} md={6}>
          <Card elevation={2}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                📈 Market Analysis
              </Typography>
              
              <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                <Chip 
                  label={market_analysis.volatility_level || 'Unknown'}
                  color={market_analysis.volatility_level === 'normal' ? 'success' : 'error'}
                  size="small"
                />
                <Chip 
                  label={market_analysis.risk_level || 'Unknown'}
                  color={market_analysis.risk_level === 'low' ? 'success' : 
                         market_analysis.risk_level === 'medium' ? 'warning' : 'error'}
                  size="small"
                />
                <Chip 
                  label={market_analysis.trading_safe ? 'Trading Safe' : 'Trading Halted'}
                  color={market_analysis.trading_safe ? 'success' : 'error'}
                  size="small"
                />
              </Box>
              
              {market_analysis.iv_percentage !== undefined && (
                <Box sx={{ mb: 1 }}>
                  <Typography variant="body2">IV Usage: {market_analysis.iv_percentage.toFixed(1)}%</Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={market_analysis.iv_percentage}
                    color={market_analysis.iv_percentage > 80 ? 'error' : 'success'}
                    sx={{ height: 4 }}
                  />
                </Box>
              )}
              
              {market_analysis.position_utilization !== undefined && (
                <Box>
                  <Typography variant="body2">Position Usage: {market_analysis.position_utilization.toFixed(1)}%</Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={market_analysis.position_utilization}
                    color={market_analysis.position_utilization > 80 ? 'warning' : 'success'}
                    sx={{ height: 4 }}
                  />
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Next Decision Point */}
        <Grid item xs={12} md={6}>
          <Card elevation={2}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                ⏰ Next Decision Point
              </Typography>
              
              <Typography variant="body1" sx={{ mb: 1 }}>
                {next_decision_point.description || 'Unknown'}
              </Typography>
              
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip 
                  icon={<Schedule />}
                  label={`~${next_decision_point.estimated_seconds || 0}s`}
                  size="small"
                  variant="outlined"
                />
                <Chip 
                  label={next_decision_point.type || 'Unknown'}
                  size="small"
                  color="primary"
                />
              </Box>
              
              {next_decision_point.trigger && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  Trigger: {next_decision_point.trigger}
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Alternative Scenarios */}
        {alternative_scenarios.length > 0 && (
          <Grid item xs={12}>
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="h6">
                  🎯 Alternative Scenarios ({alternative_scenarios.length})
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Grid container spacing={2}>
                  {alternative_scenarios.map((scenario, index) => (
                    <Grid item xs={12} md={6} key={index}>
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

        {/* Risk Factors */}
        {risk_factors.length > 0 && (
          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" gutterBottom sx={{ color: '#f44336' }}>
                  ⚠️ Risk Factors
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
                        secondary={`Impact: ${risk.impact}`}
                      />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Monitoring Alerts */}
        {monitoring_alerts.length > 0 && (
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
      </Grid>

      {/* CSS for pulse animation */}
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

export default RealTimePredictions;