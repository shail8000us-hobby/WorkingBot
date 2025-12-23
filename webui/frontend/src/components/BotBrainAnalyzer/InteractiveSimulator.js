/**
 * User-Friendly Interactive Bot Simulator
 * 
 * Enhanced simulator with better data representation, intuitive UI,
 * and step-by-step scenario exploration.
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Card,
  CardContent,
  Chip,
  Alert,
  LinearProgress,
  Grid,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Divider,
  Avatar,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Tooltip
} from '@mui/material';
import {
  PlayArrow,
  ExpandMore,
  TrendingUp,
  Security,
  Speed,
  CheckCircle,
  RadioButtonUnchecked,
  Insights,
  Timeline,
  Refresh,
  Psychology
} from '@mui/icons-material';

const InteractiveSimulator = () => {
  const [scenarioData, setScenarioData] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [currentSimulation, setCurrentSimulation] = useState(null);
  const [simulationStep, setSimulationStep] = useState(0);
  const [loading, setLoading] = useState(false);

  const fetchScenarios = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/brain/interactive/scenarios');
      const data = await response.json();
      
      if (data.success) {
        setScenarioData(data.data);
      }
    } catch (error) {
      console.error('Error fetching scenarios:', error);
    } finally {
      setLoading(false);
    }
  };

  const simulateScenario = async (scenarioId) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/brain/interactive/simulate/${scenarioId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ step: simulationStep })
      });
      
      const data = await response.json();
      if (data.success) {
        setCurrentSimulation(data.simulation);
        setSimulationStep(prev => prev + 1);
        
        // Auto-scroll to results
        setTimeout(() => {
          const element = document.getElementById('simulation-results');
          if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }, 300);
      }
    } catch (error) {
      console.error('Error simulating scenario:', error);
    } finally {
      setLoading(false);
    }
  };

  const executeAction = async (actionId) => {
    if (currentSimulation) {
      await simulateScenario(currentSimulation.scenario_id);
    }
  };

  const resetSimulation = () => {
    setCurrentSimulation(null);
    setSimulationStep(0);
    setSelectedCategory(null);
    fetchScenarios();
  };

  useEffect(() => {
    fetchScenarios();
  }, []);

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return '#4caf50';
    if (confidence >= 0.6) return '#ff9800';
    return '#f44336';
  };

  const getRiskColor = (riskLevel) => {
    switch (riskLevel) {
      case 'low': return '#4caf50';
      case 'medium': return '#ff9800';
      case 'high': return '#f44336';
      default: return '#2196f3';
    }
  };

  if (loading && !scenarioData) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center' }}>
        <LinearProgress sx={{ mb: 2 }} />
        <Typography>Loading interactive simulator...</Typography>
      </Paper>
    );
  }

  return (
    <Box sx={{ mt: 2 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
          🎮 Interactive Bot Simulator
          <Chip label="USER FRIENDLY" size="small" sx={{ bgcolor: '#4caf50', color: '#fff' }} />
        </Typography>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={resetSimulation}
          disabled={loading}
        >
          Reset
        </Button>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        <Typography variant="body2">
          <strong>🚀 Explore Bot Decisions:</strong> Step through real bot scenarios to understand 
          how the trading system makes decisions. Each scenario uses actual bot logic and current market data.
        </Typography>
      </Alert>

      {/* Current State Overview */}
      {scenarioData?.current_state && (
        <Card elevation={2} sx={{ mb: 3, bgcolor: '#1e1e1e', border: '1px solid #333' }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1, color: '#fff' }}>
              🔍 Current Bot State
              <Chip 
                label={`${(scenarioData.current_state.confidence * 100).toFixed(0)}% Confidence`}
                sx={{ bgcolor: getConfidenceColor(scenarioData.current_state.confidence), color: '#fff' }}
              />
            </Typography>
            
            <Typography variant="h5" sx={{ mb: 1, fontWeight: 'bold', color: '#64b5f6' }}>
              {scenarioData.current_state.title}
            </Typography>
            
            <Typography variant="body1" sx={{ mb: 2, color: '#e0e0e0' }}>
              {scenarioData.current_state.description}
            </Typography>

            {scenarioData.current_state.data && Object.keys(scenarioData.current_state.data).length > 0 && (
              <Grid container spacing={2}>
                {Object.entries(scenarioData.current_state.data).slice(0, 6).map(([key, value]) => (
                  <Grid item xs={6} sm={4} md={2} key={key}>
                    <Paper variant="outlined" sx={{ p: 1, textAlign: 'center', bgcolor: '#2a2a2a', border: '1px solid #444' }}>
                      <Typography variant="caption" sx={{ color: '#bbb' }}>
                        {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </Typography>
                      <Typography variant="body2" sx={{ fontWeight: 'bold', color: '#fff' }}>
                        {typeof value === 'boolean' ? (value ? '✅' : '❌') : String(value)}
                      </Typography>
                    </Paper>
                  </Grid>
                ))}
              </Grid>
            )}
          </CardContent>
        </Card>
      )}

      {/* Scenario Categories */}
      {scenarioData?.categories && !currentSimulation && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h5" sx={{ mb: 2, fontWeight: 'bold', color: '#fff' }}>
            📚 Explore Bot Decision Categories
          </Typography>
          
          <Grid container spacing={2}>
            {Object.entries(scenarioData.categories).map(([categoryId, category]) => (
              <Grid item xs={12} md={6} lg={4} key={categoryId}>
                <Card 
                  elevation={selectedCategory === categoryId ? 4 : 2}
                  sx={{ 
                    height: '100%',
                    cursor: 'pointer',
                    bgcolor: '#1e1e1e',
                    border: selectedCategory === categoryId ? '2px solid #64b5f6' : '1px solid #333',
                    '&:hover': { elevation: 4, transform: 'translateY(-2px)', bgcolor: '#2a2a2a' },
                    transition: 'all 0.2s'
                  }}
                  onClick={() => setSelectedCategory(selectedCategory === categoryId ? null : categoryId)}
                >
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                      <Avatar sx={{ bgcolor: '#64b5f6', fontSize: '1.5rem' }}>
                        {category.icon}
                      </Avatar>
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#fff' }}>
                          {category.name}
                        </Typography>
                        <Chip 
                          label={`${category.count} scenarios`} 
                          size="small" 
                          sx={{ bgcolor: '#333', color: '#fff' }}
                        />
                      </Box>
                    </Box>
                    
                    <Typography variant="body2" sx={{ mb: 2, color: '#bbb' }}>
                      {category.description}
                    </Typography>

                    {selectedCategory === categoryId && (
                      <Box sx={{ mt: 2 }}>
                        <Divider sx={{ mb: 2 }} />
                        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold', color: '#fff' }}>
                          Available Scenarios:
                        </Typography>
                        
                        {category.scenarios.slice(0, 3).map((scenario) => (
                          <Button
                            key={scenario.id}
                            variant="outlined"
                            fullWidth
                            size="small"
                            sx={{ mb: 1, justifyContent: 'flex-start' }}
                            onClick={(e) => {
                              e.stopPropagation();
                              simulateScenario(scenario.id);
                            }}
                          >
                            <Box sx={{ textAlign: 'left', flex: 1 }}>
                              <Typography variant="body2" sx={{ fontWeight: 'bold', color: '#fff' }}>
                                {scenario.title}
                              </Typography>
                              <Typography variant="caption" sx={{ color: '#bbb' }}>
                                {(scenario.confidence * 100).toFixed(0)}% confidence
                              </Typography>
                            </Box>
                          </Button>
                        ))}
                        
                        {category.scenarios.length > 3 && (
                          <Typography variant="caption" sx={{ color: '#bbb' }}>
                            +{category.scenarios.length - 3} more scenarios...
                          </Typography>
                        )}
                      </Box>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* Featured Scenarios */}
      {scenarioData?.featured_scenarios && !currentSimulation && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h5" sx={{ mb: 2, fontWeight: 'bold', color: '#fff' }}>
            ⭐ High-Confidence Scenarios
          </Typography>
          
          <Grid container spacing={2}>
            {scenarioData.featured_scenarios.slice(0, 6).map((scenario) => (
              <Grid item xs={12} sm={6} md={4} key={scenario.id}>
                <Card elevation={2} sx={{ height: '100%', bgcolor: '#1e1e1e', border: '1px solid #333' }}>
                  <CardContent>
                    <Typography variant="h6" sx={{ mb: 1, fontWeight: 'bold', color: '#fff' }}>
                      {scenario.title}
                    </Typography>
                    
                    <Typography variant="body2" sx={{ mb: 2, color: '#bbb' }}>
                      {scenario.description}
                    </Typography>
                    
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                      <Chip 
                        label={scenario.category.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                        size="small"
                        sx={{ bgcolor: '#333', color: '#fff' }}
                      />
                      <Chip 
                        label={`${(scenario.confidence * 100).toFixed(0)}%`}
                        sx={{ bgcolor: getConfidenceColor(scenario.confidence), color: '#fff' }}
                      />
                    </Box>
                    
                    <Button
                      variant="contained"
                      startIcon={<PlayArrow />}
                      fullWidth
                      onClick={() => simulateScenario(scenario.id)}
                    >
                      Simulate
                    </Button>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* Current Simulation Results */}
      {currentSimulation && (
        <Card elevation={3} id="simulation-results" sx={{ mb: 3, border: '3px solid #4caf50', bgcolor: '#1e1e1e' }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="h4" sx={{ fontWeight: 'bold', color: '#4caf50' }}>
                🎯 Simulation Results
              </Typography>
              <Chip 
                label={`Step ${currentSimulation.step}`}
                sx={{ bgcolor: '#4caf50', color: '#fff', fontSize: '1rem' }}
              />
            </Box>
            
            {/* Current State */}
            <Card variant="outlined" sx={{ mb: 3, bgcolor: '#2a2a2a', border: '1px solid #444' }}>
              <CardContent>
                <Typography variant="h5" sx={{ mb: 2, fontWeight: 'bold', color: '#64b5f6' }}>
                  {currentSimulation.scenario_title}
                </Typography>
                
                <Alert severity="info" sx={{ mb: 2 }}>
                  <Typography variant="body1">
                    <strong>Current State:</strong> {currentSimulation.current_state.title}
                  </Typography>
                </Alert>
                
                <Typography variant="body1" sx={{ mb: 2, color: '#e0e0e0' }}>
                  {currentSimulation.current_state.description}
                </Typography>
                
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Chip 
                    label={`${(currentSimulation.current_state.confidence * 100).toFixed(0)}% Confidence`}
                    sx={{ bgcolor: getConfidenceColor(currentSimulation.current_state.confidence), color: '#fff' }}
                  />
                  <Typography variant="body2" sx={{ color: '#bbb' }}>
                    Based on real-time bot analysis
                  </Typography>
                </Box>
              </CardContent>
            </Card>

            {/* Real-Time Data Insights */}
            {currentSimulation.insights && currentSimulation.insights.length > 0 && (
              <Card variant="outlined" sx={{ mb: 3, bgcolor: '#2a2a2a', border: '1px solid #444' }}>
                <CardContent>
                  <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1, color: '#fff' }}>
                    <Insights /> Real-Time Data
                  </Typography>
                  
                  <Grid container spacing={2}>
                    {currentSimulation.insights.map((insight, index) => (
                      <Grid item xs={6} sm={4} md={3} key={index}>
                        <Paper variant="outlined" sx={{ p: 2, textAlign: 'center', bgcolor: '#333', border: '1px solid #555' }}>
                          <Typography variant="body2" sx={{ color: '#bbb' }}>
                            {insight.title}
                          </Typography>
                          <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#64b5f6' }}>
                            {insight.formatted_value}
                          </Typography>
                        </Paper>
                      </Grid>
                    ))}
                  </Grid>
                </CardContent>
              </Card>
            )}

            {/* Possible Actions */}
            {currentSimulation.possible_actions && currentSimulation.possible_actions.length > 0 && (
              <Card variant="outlined" sx={{ mb: 3, bgcolor: '#2a2a2a', border: '1px solid #444' }}>
                <CardContent>
                  <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1, color: '#fff' }}>
                    🎮 Bot's Next Actions
                    <Chip label="Choose One" size="small" sx={{ bgcolor: '#ff9800', color: '#fff' }} />
                  </Typography>
                  
                  <Grid container spacing={2}>
                    {currentSimulation.possible_actions.map((action, index) => (
                      <Grid item xs={12} sm={6} key={action.id}>
                        <Button
                          variant="contained"
                          fullWidth
                          size="large"
                          disabled={loading}
                          sx={{ 
                            p: 2, 
                            textAlign: 'left',
                            bgcolor: getRiskColor(action.risk_level),
                            '&:hover': {
                              bgcolor: getRiskColor(action.risk_level),
                              opacity: 0.8
                            }
                          }}
                          onClick={() => executeAction(action.id)}
                        >
                          <Box sx={{ width: '100%' }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                              <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                                {action.title}
                              </Typography>
                              <Chip 
                                label={action.risk_level.toUpperCase()} 
                                size="small" 
                                sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: '#fff' }}
                              />
                            </Box>
                            
                            <Typography variant="body2" sx={{ opacity: 0.9, mb: 1 }}>
                              {action.description}
                            </Typography>
                            
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <Typography variant="caption" sx={{ opacity: 0.8 }}>
                                ⏱️ {action.estimated_time}
                              </Typography>
                              <Typography variant="caption" sx={{ opacity: 0.8 }}>
                                🎯 {(action.confidence * 100).toFixed(0)}% success
                              </Typography>
                            </Box>
                          </Box>
                        </Button>
                      </Grid>
                    ))}
                  </Grid>
                </CardContent>
              </Card>
            )}

            {/* Next Steps Preview */}
            {currentSimulation.next_steps && currentSimulation.next_steps.length > 0 && (
              <Card variant="outlined" sx={{ bgcolor: '#2a2a2a', border: '1px solid #444' }}>
                <CardContent>
                  <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1, color: '#fff' }}>
                    <Timeline /> Expected Outcomes
                  </Typography>
                  
                  <List>
                    {currentSimulation.next_steps.map((step, index) => (
                      <ListItem key={index}>
                        <ListItemIcon>
                          <CheckCircle sx={{ color: '#4caf50' }} />
                        </ListItemIcon>
                        <ListItemText
                          primary={step.title}
                          secondary={
                            <Box>
                              <Typography variant="body2" sx={{ color: '#bbb' }}>
                                {step.description}
                              </Typography>
                              <Chip 
                                label={`${(step.probability * 100).toFixed(0)}% probability`}
                                size="small"
                                sx={{ mt: 0.5, bgcolor: '#333', color: '#fff' }}
                              />
                            </Box>
                          }
                        />
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            )}

            {/* Continue Simulation */}
            <Box sx={{ mt: 3, textAlign: 'center' }}>
              <Button
                variant="outlined"
                size="large"
                startIcon={<Psychology />}
                onClick={() => simulateScenario(currentSimulation.scenario_id)}
                disabled={loading}
                sx={{ mr: 2 }}
              >
                Continue Simulation
              </Button>
              
              <Button
                variant="text"
                onClick={resetSimulation}
                disabled={loading}
              >
                Try Different Scenario
              </Button>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Stats Footer */}
      {scenarioData?.stats && (
        <Paper variant="outlined" sx={{ p: 2, mt: 3, bgcolor: '#1e1e1e', border: '1px solid #333' }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={3}>
              <Typography variant="body2" sx={{ color: '#bbb' }}>Total Scenarios</Typography>
              <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#fff' }}>
                {scenarioData.stats.total_scenarios}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Typography variant="body2" sx={{ color: '#bbb' }}>Data Freshness</Typography>
              <Chip 
                label={scenarioData.stats.data_freshness.toUpperCase()}
                size="small"
                sx={{ bgcolor: '#4caf50', color: '#fff' }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" sx={{ color: '#bbb' }}>
                Last updated: {new Date(scenarioData.stats.last_scan * 1000).toLocaleString()}
              </Typography>
            </Grid>
          </Grid>
        </Paper>
      )}
    </Box>
  );
};

export default InteractiveSimulator;