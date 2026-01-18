/**
 * Simple Trading Simulator
 * 
 * Focused on only two critical scenarios:
 * 1. Trading Active - Show next BUY order and target prices
 * 2. Trading Halted - Show why and when it will resume
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Card,
  CardContent,
  Grid,
  Alert,
  LinearProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  Divider
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  TrendingUp,
  AttachMoney,
  Schedule,
  Refresh
} from '@mui/icons-material';

const SimpleTradingSimulator = () => {
  const [currentScenario, setCurrentScenario] = useState(null);
  const [scenarioDetails, setScenarioDetails] = useState(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(Date.now());

  const fetchTradingScenarios = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/brain/trading/scenarios');
      const data = await response.json();
      
      if (data.success) {
        setCurrentScenario(data.current_scenario);
      }
    } catch (error) {
      console.error('Error fetching trading scenarios:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchScenarioDetails = async (scenarioId, step = 0) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/brain/trading/details/${scenarioId}?step=${step}`);
      const data = await response.json();
      
      if (data.success) {
        setScenarioDetails(data);
        setCurrentStep(data.step);
      }
    } catch (error) {
      console.error('Error fetching scenario details:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleExploreScenario = (scenarioId) => {
    setCurrentStep(0);
    fetchScenarioDetails(scenarioId, 0);
  };

  const handleNextStep = () => {
    if (currentScenario) {
      fetchScenarioDetails(currentScenario.id, currentStep);
    }
  };

  const handleReset = () => {
    setScenarioDetails(null);
    setCurrentStep(0);
    fetchTradingScenarios();
  };

  useEffect(() => {
    fetchTradingScenarios();
    
    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      fetchTradingScenarios();
      setLastRefresh(Date.now());
      
      // If viewing scenario details, refresh them too
      if (scenarioDetails && currentScenario) {
        fetchScenarioDetails(currentScenario.id, currentStep - 1);
      }
    }, 30000);
    
    return () => clearInterval(interval);
  }, [scenarioDetails, currentScenario, currentStep]);

  if (loading && !currentScenario) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center', bgcolor: '#1e1e1e', border: '1px solid #333' }}>
        <LinearProgress sx={{ mb: 2 }} />
        <Typography sx={{ color: '#fff' }}>Loading trading status...</Typography>
      </Paper>
    );
  }

  return (
    <Box sx={{ mt: 2 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold', color: '#fff', display: 'flex', alignItems: 'center', gap: 1 }}>
          📈 Trading Simulator
          <Chip label="SIMPLIFIED" size="small" sx={{ bgcolor: '#2196f3', color: '#fff' }} />
        </Typography>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={handleReset}
          disabled={loading}
          sx={{ color: '#fff', borderColor: '#555' }}
        >
          Refresh
        </Button>
      </Box>

      <Alert severity="info" sx={{ mb: 3, bgcolor: '#1a237e', color: '#fff', border: '1px solid #3f51b5' }}>
        <Typography variant="body2">
          <strong>🎯 Focus on What Matters:</strong> Only two scenarios matter in trading - 
          Active (buying/selling) or Halted (waiting). Auto-refreshes every 30 seconds.
          <br />
          <Typography variant="caption" sx={{ opacity: 0.8, mt: 1, display: 'block' }}>
            Last updated: {new Date(lastRefresh).toLocaleTimeString()}
          </Typography>
        </Typography>
      </Alert>

      {/* Current Scenario Overview */}
      {currentScenario && !scenarioDetails && (
        <Card elevation={3} sx={{ mb: 3, bgcolor: '#1e1e1e', border: `3px solid ${currentScenario.color}` }}>
          <CardContent>
            <Box sx={{ textAlign: 'center', py: 3 }}>
              <Typography variant="h1" sx={{ fontSize: '4rem', mb: 2 }}>
                {currentScenario.icon}
              </Typography>
              
              <Typography variant="h3" sx={{ fontWeight: 'bold', color: currentScenario.color, mb: 2 }}>
                {currentScenario.title}
              </Typography>
              
              <Typography variant="h6" sx={{ color: '#e0e0e0', mb: 4 }}>
                {currentScenario.description}
              </Typography>

              {/* Quick Stats */}
              <Grid container spacing={2} sx={{ mb: 4 }}>
                {Object.entries(currentScenario.details).map(([key, value]) => (
                  <Grid item xs={12} sm={4} key={key}>
                    <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#2a2a2a', border: '1px solid #444' }}>
                      <Typography variant="body2" sx={{ color: '#bbb', mb: 1 }}>
                        {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </Typography>
                      <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#fff' }}>
                        {value}
                      </Typography>
                    </Paper>
                  </Grid>
                ))}
              </Grid>

              <Button
                variant="contained"
                size="large"
                startIcon={currentScenario.status === 'active' ? <PlayArrow /> : <Stop />}
                onClick={() => handleExploreScenario(currentScenario.id)}
                sx={{ 
                  bgcolor: currentScenario.color,
                  color: '#fff',
                  px: 4,
                  py: 2,
                  fontSize: '1.2rem',
                  '&:hover': {
                    bgcolor: currentScenario.color,
                    opacity: 0.8
                  }
                }}
              >
                {currentScenario.status === 'active' ? 'Explore Active Trading' : 'Why is Trading Halted?'}
              </Button>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Scenario Details */}
      {scenarioDetails && (
        <Card elevation={3} sx={{ mb: 3, bgcolor: '#1e1e1e', border: '2px solid #4caf50' }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="h4" sx={{ fontWeight: 'bold', color: '#4caf50' }}>
                {scenarioDetails.title}
              </Typography>
              <Chip 
                label={`Step ${scenarioDetails.step}`}
                sx={{ bgcolor: '#4caf50', color: '#fff', fontSize: '1rem' }}
              />
            </Box>

            <Typography variant="h6" sx={{ color: '#e0e0e0', mb: 3 }}>
              {scenarioDetails.description}
            </Typography>

            {/* Data Display */}
            {scenarioDetails.data && (
              <Box sx={{ mb: 4 }}>
                {scenarioDetails.data.target_orders ? (
                  // Special handling for target orders
                  <Box>
                    <Typography variant="h6" sx={{ color: '#fff', mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                      <AttachMoney /> Active Target Orders
                    </Typography>
                    <List>
                      {scenarioDetails.data.target_orders.map((order, index) => (
                        <ListItem key={index} sx={{ bgcolor: '#2a2a2a', mb: 1, borderRadius: 1 }}>
                          <ListItemText
                            primary={
                              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <Typography sx={{ color: '#fff', fontWeight: 'bold' }}>
                                  Entry: {order.entry_price}
                                </Typography>
                                <Typography sx={{ color: '#4caf50', fontWeight: 'bold' }}>
                                  Target: {order.target_price}
                                </Typography>
                                <Typography sx={{ color: '#ff9800', fontWeight: 'bold' }}>
                                  Profit: {order.profit}
                                </Typography>
                              </Box>
                            }
                          />
                        </ListItem>
                      ))}
                    </List>
                    {scenarioDetails.data.total_positions > scenarioDetails.data.target_orders.length && (
                      <Typography variant="body2" sx={{ color: '#bbb', mt: 1 }}>
                        +{scenarioDetails.data.total_positions - scenarioDetails.data.target_orders.length} more positions...
                      </Typography>
                    )}
                  </Box>
                ) : (
                  // Regular data display
                  <Grid container spacing={2}>
                    {Object.entries(scenarioDetails.data).map(([key, value]) => (
                      <Grid item xs={12} sm={6} md={4} key={key}>
                        <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#2a2a2a', border: '1px solid #444' }}>
                          <Typography variant="body2" sx={{ color: '#bbb', mb: 1 }}>
                            {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                          </Typography>
                          <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#fff' }}>
                            {value}
                          </Typography>
                        </Paper>
                      </Grid>
                    ))}
                  </Grid>
                )}
              </Box>
            )}

            {/* Action Buttons */}
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
              {scenarioDetails.next_button && (
                <Button
                  variant="contained"
                  size="large"
                  startIcon={<TrendingUp />}
                  onClick={handleNextStep}
                  disabled={loading}
                  sx={{ 
                    bgcolor: '#2196f3',
                    color: '#fff',
                    px: 3,
                    py: 1.5,
                    '&:hover': {
                      bgcolor: '#1976d2'
                    }
                  }}
                >
                  {scenarioDetails.next_button}
                </Button>
              )}
              
              <Button
                variant="outlined"
                size="large"
                startIcon={<Schedule />}
                onClick={handleReset}
                disabled={loading}
                sx={{ 
                  color: '#fff',
                  borderColor: '#555',
                  px: 3,
                  py: 1.5,
                  '&:hover': {
                    borderColor: '#777',
                    bgcolor: '#2a2a2a'
                  }
                }}
              >
                Back to Overview
              </Button>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Info Footer */}
      <Paper sx={{ p: 2, bgcolor: '#1e1e1e', border: '1px solid #333' }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={8}>
            <Typography variant="body2" sx={{ color: '#bbb' }}>
              💡 <strong>Simple & Focused:</strong> Shows only what matters - 
              whether the bot is actively trading or waiting, and what happens next.
            </Typography>
          </Grid>
          <Grid item xs={12} sm={4} sx={{ textAlign: { xs: 'center', sm: 'right' } }}>
            <Typography variant="caption" sx={{ color: '#888' }}>
              🔄 Auto-refresh: 30s
              <br />
              Last: {new Date(lastRefresh).toLocaleTimeString()}
            </Typography>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default SimpleTradingSimulator;