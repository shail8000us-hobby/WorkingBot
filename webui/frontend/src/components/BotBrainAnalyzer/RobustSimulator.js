/**
 * Robust Interactive Bot Simulator
 *
 * Production-ready simulator that integrates with existing brain analyzer components.
 * Uses strategy analysis, decision flow, and action sequences for comprehensive simulation.
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
  List,
  ListItem,
  ListItemText,
  Tabs,
  Tab,
} from '@mui/material';
import {
  PlayArrow,
  Psychology,
  CheckCircle,
  Warning,
  Refresh,
  TrendingUp,
  Security,
  Speed,
} from '@mui/icons-material';

const RobustSimulator = () => {
  const [simulationTree, setSimulationTree] = useState(null);
  const [currentSimulation, setCurrentSimulation] = useState(null);
  const [simulationHistory, setSimulationHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState(0);

  const fetchSimulationTree = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/brain/simulation-tree');
      const data = await response.json();

      if (data.success) {
        setSimulationTree(data);
      }
    } catch (error) {
      console.error('Error fetching simulation tree:', error);
    } finally {
      setLoading(false);
    }
  };

  const simulateScenario = async (scenario, steps = []) => {
    try {
      setLoading(true);
      const response = await fetch('/api/brain/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario, steps }),
      });

      const data = await response.json();
      if (data.success) {
        setCurrentSimulation(data);

        // Add to history
        const historyEntry = {
          scenario,
          steps: [...steps],
          result: data,
          timestamp: new Date(),
        };
        setSimulationHistory((prev) => [...prev, historyEntry]);

        // Auto-scroll to simulation results
        setTimeout(() => {
          const simulationElement = document.getElementById('simulation-results');
          if (simulationElement) {
            simulationElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }, 300);
      }
    } catch (error) {
      console.error('Error simulating scenario:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleChoice = (choice) => {
    if (currentSimulation) {
      const newSteps = [...(currentSimulation.steps || []), choice];
      simulateScenario(currentSimulation.scenario, newSteps);
    }
  };

  const resetSimulation = () => {
    setCurrentSimulation(null);
    setSimulationHistory([]);
    fetchSimulationTree();
  };

  useEffect(() => {
    fetchSimulationTree();
  }, []);

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return '#4caf50';
    if (confidence >= 0.6) return '#ff9800';
    return '#f44336';
  };

  const getScenarioIcon = (scenarioId) => {
    switch (scenarioId) {
      case 'current':
        return <Psychology />;
      case 'volatility_safe':
        return <CheckCircle />;
      case 'volatility_unsafe':
        return <Warning />;
      case 'position_limit':
        return <Security />;
      case 'grid_expansion':
        return <TrendingUp />;
      default:
        return <Speed />;
    }
  };

  if (loading && !simulationTree) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center' }}>
        <LinearProgress sx={{ mb: 2 }} />
        <Typography>Loading robust bot simulator...</Typography>
      </Paper>
    );
  }

  return (
    <Box sx={{ mt: 2 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography
          variant="h5"
          sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}
        >
          🚀 Robust Bot Simulator
          <Chip label="PRODUCTION" size="small" sx={{ bgcolor: '#2196f3', color: '#fff' }} />
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
          <strong>Production-Ready Simulator:</strong> Integrates with strategy analysis, decision
          flow, and action sequences. Uses actual bot logic without interfering with operations.
        </Typography>
      </Alert>

      <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)} sx={{ mb: 3 }}>
        <Tab label="🎯 Scenarios" />
        <Tab label="📊 Current State" />
        <Tab label="📝 History" />
      </Tabs>

      {/* Scenarios Tab */}
      {activeTab === 0 && simulationTree && (
        <Grid container spacing={3}>
          {simulationTree.simulation_tree.scenarios.map((scenario, index) => (
            <Grid item xs={12} md={6} key={scenario.id}>
              <Card
                elevation={2}
                sx={{
                  height: '100%',
                  cursor: 'pointer',
                  '&:hover': { elevation: 4, transform: 'translateY(-2px)' },
                  transition: 'all 0.2s',
                }}
                onClick={() => simulateScenario(scenario.id)}
              >
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                    {getScenarioIcon(scenario.id)}
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                        {scenario.title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {scenario.description}
                      </Typography>
                    </Box>
                    <Chip
                      label={`${(scenario.confidence * 100).toFixed(0)}%`}
                      sx={{
                        bgcolor: getConfidenceColor(scenario.confidence),
                        color: '#fff',
                      }}
                    />
                  </Box>

                  {scenario.details && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                        Details:
                      </Typography>
                      {Object.entries(scenario.details).map(([key, value]) => (
                        <Box
                          key={key}
                          sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}
                        >
                          <Typography variant="body2" color="text.secondary">
                            {key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}:
                          </Typography>
                          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                            {typeof value === 'number' && key.includes('price')
                              ? `₹${value.toLocaleString()}`
                              : String(value)}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  )}

                  <Button
                    variant="contained"
                    startIcon={<PlayArrow />}
                    fullWidth
                    sx={{ mt: 2 }}
                    onClick={(e) => {
                      e.stopPropagation();
                      simulateScenario(scenario.id);
                    }}
                  >
                    Simulate This Scenario
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Current State Tab */}
      {activeTab === 1 && simulationTree && (
        <Card elevation={2}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              📊 Current Bot State
            </Typography>

            <Grid container spacing={2}>
              {Object.entries(simulationTree.simulation_tree.current_state).map(([key, value]) => (
                <Grid item xs={12} sm={6} md={4} key={key}>
                  <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                    <Typography variant="body2" color="text.secondary">
                      {key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                      {typeof value === 'boolean'
                        ? value
                          ? '✅'
                          : '❌'
                        : typeof value === 'number' && key.includes('confidence')
                          ? `${(value * 100).toFixed(0)}%`
                          : String(value)}
                    </Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Current Simulation Results */}
      {currentSimulation && (
        <Card elevation={3} id="simulation-results" sx={{ mb: 3, border: '2px solid #2196f3' }}>
          <CardContent>
            <Typography variant="h5" sx={{ mb: 2, fontWeight: 'bold', color: '#2196f3' }}>
              🎯 Simulation Results
            </Typography>

            <Alert severity="success" sx={{ mb: 3 }}>
              <Typography variant="body1">
                <strong>Scenario:</strong> {currentSimulation.scenario} |<strong>Step:</strong>{' '}
                {currentSimulation.step || 1}
              </Typography>
            </Alert>

            <Card variant="outlined" sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                  {currentSimulation.decision?.title}
                </Typography>
                <Typography variant="body1" sx={{ mb: 2 }}>
                  {currentSimulation.decision?.description}
                </Typography>

                {currentSimulation.decision?.details && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                      Details:
                    </Typography>
                    <Grid container spacing={1}>
                      {Object.entries(currentSimulation.decision.details).map(([key, value]) => (
                        <Grid item xs={12} sm={6} key={key}>
                          <Paper variant="outlined" sx={{ p: 1 }}>
                            <Typography variant="caption" color="text.secondary">
                              {key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                            </Typography>
                            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                              {typeof value === 'number' && key.includes('price')
                                ? `₹${value.toLocaleString()}`
                                : String(value)}
                            </Typography>
                          </Paper>
                        </Grid>
                      ))}
                    </Grid>
                  </Box>
                )}
              </CardContent>
            </Card>

            {currentSimulation.options && currentSimulation.options.length > 0 ? (
              <Box>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                  🎮 Next Actions (Choose Bot's Next Step):
                </Typography>
                <Grid container spacing={2}>
                  {currentSimulation.options.map((option, index) => (
                    <Grid item xs={12} sm={6} key={option.id}>
                      <Button
                        variant="contained"
                        fullWidth
                        size="large"
                        disabled={loading}
                        sx={{
                          p: 2,
                          textAlign: 'left',
                          bgcolor: index === 0 ? '#4caf50' : '#ff9800',
                          '&:hover': {
                            bgcolor: index === 0 ? '#45a049' : '#f57c00',
                          },
                        }}
                        onClick={() => handleChoice(option.choice)}
                      >
                        <Box>
                          <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                            {option.title}
                          </Typography>
                          {option.description && (
                            <Typography variant="body2" sx={{ opacity: 0.9 }}>
                              {option.description}
                            </Typography>
                          )}
                        </Box>
                      </Button>
                    </Grid>
                  ))}
                </Grid>
              </Box>
            ) : (
              <Alert severity="success" sx={{ mt: 2 }}>
                <Typography variant="body2">
                  <strong>Simulation Complete!</strong> This decision path has reached its
                  conclusion. Try other scenarios or reset to start fresh.
                </Typography>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* History Tab */}
      {activeTab === 2 && (
        <Card elevation={2}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              📝 Simulation History
            </Typography>

            {simulationHistory.length === 0 ? (
              <Alert severity="info">
                No simulations run yet. Click on a scenario above to start!
              </Alert>
            ) : (
              <List>
                {simulationHistory.map((entry, index) => (
                  <ListItem key={index} divider>
                    <ListItemText
                      primary={`${entry.scenario} - Step ${entry.steps.length + 1}`}
                      secondary={`${entry.timestamp.toLocaleTimeString()} - ${entry.result.decision?.title}`}
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default RobustSimulator;
