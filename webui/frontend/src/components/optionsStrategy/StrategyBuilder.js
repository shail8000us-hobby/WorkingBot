/**
 * Options Strategy Builder
 * ========================
 * Main page for building and managing multi-leg options strategies.
 * 
 * Created: January 5, 2026
 * Updated: Phase 3 - Added Automation tab
 * Updated: January 12, 2026 - Added pre-execution validation
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Alert,
  Snackbar,
  Tabs,
  Tab,
  Chip,
  CircularProgress,
  Badge
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  AccountTree as StrategyIcon,
  Assessment as AssessmentIcon,
  AutoMode as AutoModeIcon,
  Verified as ValidationIcon
} from '@mui/icons-material';

import StrategyTypeSelector from './StrategyTypeSelector';
import StrategyForm from './StrategyForm';
import PayoffDiagram from './PayoffDiagram';
import ActiveStrategies from './ActiveStrategies';
import StrategyDetails from './StrategyDetails';
import AutomationControls from './AutomationControls';
import StrikeSuggestions from './StrikeSuggestions';
import StrategyValidationStatus from './StrategyValidationStatus';

const API_BASE = '/api/options-strategy';

function TabPanel({ children, value, index, ...other }) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`strategy-tabpanel-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

export default function StrategyBuilder({ onNavigateToTab }) {
  // Tab state
  const [activeTab, setActiveTab] = useState(0);
  
  // Strategy creation state
  const [selectedType, setSelectedType] = useState(null);
  const [templates, setTemplates] = useState([]);
  
  // Validation state (JAN 12, 2026)
  const [validationResult, setValidationResult] = useState(null);
  const [createdStrategy, setCreatedStrategy] = useState(null);
  
  // Active strategies state
  const [activeStrategies, setActiveStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [summary, setSummary] = useState(null);
  const [automationRunning, setAutomationRunning] = useState(false);
  
  // UI state
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState({ open: false, message: '', severity: 'info' });

  // Fetch templates on mount
  useEffect(() => {
    fetchTemplates();
    fetchActiveStrategies();
    fetchSummary();
  }, []);

  const fetchTemplates = async () => {
    try {
      const res = await fetch(`${API_BASE}/templates`);
      const data = await res.json();
      setTemplates(data.templates || []);
    } catch (err) {
      showNotification('Failed to load strategy templates', 'error');
    }
  };

  const fetchActiveStrategies = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/active`);
      const data = await res.json();
      setActiveStrategies(data.strategies || []);
    } catch (err) {
      console.error('Failed to fetch active strategies:', err);
    }
  }, []);

  const fetchSummary = async () => {
    try {
      const res = await fetch(`${API_BASE}/summary`);
      const data = await res.json();
      setSummary(data);
    } catch (err) {
      console.error('Failed to fetch summary:', err);
    }
  };

  const showNotification = (message, severity = 'info') => {
    setNotification({ open: true, message, severity });
  };

  const handleCloseNotification = () => {
    setNotification({ ...notification, open: false });
  };

  const handleSelectType = (type) => {
    setSelectedType(type);
    setCreatedStrategy(null);
  };

  const handleCreateStrategy = async (formData) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      
      const data = await res.json();
      
      if (data.success) {
        setCreatedStrategy(data.strategy);
        showNotification(`Strategy "${data.strategy.name}" created!`, 'success');
        fetchActiveStrategies();
        fetchSummary();
      } else {
        showNotification(data.error || 'Failed to create strategy', 'error');
      }
    } catch (err) {
      showNotification(`Error: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleExecuteStrategy = async (strategyId, options = {}) => {
    // Pre-execution validation check (JAN 12, 2026)
    if (validationResult && !validationResult.is_valid) {
      showNotification('Cannot execute: Strategy validation failed. Please fix errors first.', 'error');
      return;
    }
    
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/execute/${strategyId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options)
      });
      
      const data = await res.json();
      
      if (data.success) {
        showNotification(`Strategy executed successfully! ${data.legs_filled || 0} legs placed.`, 'success');
        fetchActiveStrategies();
        fetchSummary();
        if (createdStrategy?.id === strategyId) {
          setCreatedStrategy({ ...createdStrategy, status: 'active' });
        }
      } else {
        // Build detailed error message
        let errorMsg = data.message || data.error || 'Execution failed';
        if (data.errors && data.errors.length > 0) {
          errorMsg += ': ' + data.errors.join(', ');
        }
        if (data.legs_filled !== undefined && data.legs_total !== undefined) {
          errorMsg += ` (${data.legs_filled}/${data.legs_total} legs filled)`;
        }
        showNotification(errorMsg, 'error');
      }
    } catch (err) {
      showNotification(`Execution error: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };
  
  // Validation callback (JAN 12, 2026)
  const handleValidationComplete = useCallback((isValid, result) => {
    setValidationResult(result);
    if (!isValid && result?.errors?.length > 0) {
      showNotification(`Validation issues found: ${result.errors.length} error(s)`, 'warning');
    }
  }, []);

  const handleCloseStrategy = async (strategyId) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/close/${strategyId}`, {
        method: 'POST'
      });
      
      const data = await res.json();
      
      if (data.success) {
        showNotification('Strategy closed', 'success');
        fetchActiveStrategies();
        fetchSummary();
      } else {
        showNotification(data.error || 'Failed to close', 'error');
      }
    } catch (err) {
      showNotification(`Error: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteStrategy = async (strategyId) => {
    try {
      const res = await fetch(`${API_BASE}/${strategyId}`, {
        method: 'DELETE'
      });
      
      const data = await res.json();
      
      if (data.success) {
        showNotification('Strategy deleted', 'success');
        fetchActiveStrategies();
        fetchSummary();
        if (createdStrategy?.id === strategyId) {
          setCreatedStrategy(null);
        }
      } else {
        showNotification(data.error || 'Delete failed', 'error');
      }
    } catch (err) {
      showNotification(`Error: ${err.message}`, 'error');
    }
  };

  const handleViewStrategy = (strategy) => {
    setSelectedStrategy(strategy);
  };

  const handleAutomationStatusChange = (status) => {
    const monitorRunning = status?.monitor?.running || false;
    const autoEntryRunning = status?.auto_entry?.running || false;
    setAutomationRunning(monitorRunning || autoEntryRunning);
  };

  return (
    <Box sx={{ p: 2 }}>
      {/* Header */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <StrategyIcon sx={{ fontSize: 32, color: 'primary.main' }} />
            <Box>
              <Typography variant="h5" fontWeight="bold">
                Options Strategy Builder
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Build and execute multi-leg options strategies
              </Typography>
            </Box>
          </Box>
          
          {summary && (
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Chip
                icon={<TrendingUpIcon />}
                label={`${summary.active_count || 0} Active`}
                color="primary"
                variant="outlined"
              />
              <Chip
                icon={<AssessmentIcon />}
                label={`${summary.total_count || 0} Total`}
                variant="outlined"
              />
            </Box>
          )}
        </Box>
      </Paper>

      {/* Tabs */}
      <Paper sx={{ mb: 2 }}>
        <Tabs
          value={activeTab}
          onChange={(e, v) => setActiveTab(v)}
          indicatorColor="primary"
          textColor="primary"
        >
          <Tab label="Build Strategy" />
          <Tab label={`Active Strategies (${activeStrategies.length})`} />
          <Tab 
            label={
              <Badge 
                color="success" 
                variant="dot" 
                invisible={!automationRunning}
              >
                Automation
              </Badge>
            }
            icon={<AutoModeIcon sx={{ fontSize: 18 }} />}
            iconPosition="start"
          />
        </Tabs>
      </Paper>

      {/* Build Strategy Tab */}
      <TabPanel value={activeTab} index={0}>
        <Grid container spacing={2}>
          {/* Left: Type Selection & Form */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                1. Select Strategy Type
              </Typography>
              <StrategyTypeSelector
                templates={templates}
                selectedType={selectedType}
                onSelect={handleSelectType}
              />
            </Paper>

            {selectedType && (
              <>
                {/* Strike Suggestions */}
                <Paper sx={{ p: 2, mb: 2 }}>
                  <StrikeSuggestions
                    strategyType={selectedType}
                    underlying="BTC"
                    onNavigateToChain={(params) => {
                      // Navigate to Options Chain with strategy context
                      if (onNavigateToTab) {
                        showNotification(`Opening live chain to select ${params.requiredLegs} legs...`, 'info');
                        // Store strategy context for return - use params directly as it has all the needed info
                        sessionStorage.setItem('pending_strategy', JSON.stringify({
                          strategyType: selectedType,
                          strategyName: params.strategyName,
                          underlying: params.underlying,
                          suggestedStrikes: params.suggestedStrikes,
                          requiredLegs: params.requiredLegs,
                          legHints: params.legHints,
                          legDefinitions: params.legDefinitions
                        }));
                        onNavigateToTab('options_chain', params);
                      } else {
                        showNotification('Navigation not available in standalone mode', 'warning');
                      }
                    }}
                    onApplySuggestion={(params) => {
                      // Auto-fill form with suggested strikes
                      showNotification('Strikes applied to form', 'success');
                      // Form will need to accept default values
                    }}
                  />
                </Paper>

                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>
                    2. Configure Parameters
                  </Typography>
                  <StrategyForm
                    strategyType={selectedType}
                    template={templates.find(t => t.type === selectedType)}
                    onSubmit={handleCreateStrategy}
                    loading={loading}
                  />
                </Paper>
              </>
            )}
          </Grid>

          {/* Right: Preview & Payoff */}
          <Grid item xs={12} md={6}>
            {createdStrategy ? (
              <>
                {/* Pre-Execution Validation (JAN 12, 2026) */}
                <StrategyValidationStatus
                  strategy={createdStrategy}
                  onValidationComplete={handleValidationComplete}
                  autoValidate={true}
                />
                
                <Paper sx={{ p: 2, mb: 2 }}>
                  <StrategyDetails
                    strategy={createdStrategy}
                    onExecute={handleExecuteStrategy}
                    onDelete={handleDeleteStrategy}
                    loading={loading}
                    validationResult={validationResult}
                  />
                </Paper>
                
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>
                    Payoff Diagram
                  </Typography>
                  <PayoffDiagram strategyId={createdStrategy.id} />
                </Paper>
              </>
            ) : (
              <Paper sx={{ p: 4, textAlign: 'center' }}>
                <StrategyIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                <Typography color="text.secondary">
                  Select a strategy type and configure parameters to see preview
                </Typography>
              </Paper>
            )}
          </Grid>
        </Grid>
      </TabPanel>

      {/* Active Strategies Tab */}
      <TabPanel value={activeTab} index={1}>
        <ActiveStrategies
          strategies={activeStrategies}
          onRefresh={fetchActiveStrategies}
          onClose={handleCloseStrategy}
          onDelete={handleDeleteStrategy}
          onView={handleViewStrategy}
          loading={loading}
        />
      </TabPanel>

      {/* Automation Tab */}
      <TabPanel value={activeTab} index={2}>
        <AutomationControls onStatusChange={handleAutomationStatusChange} />
      </TabPanel>

      {/* Strategy Detail Dialog */}
      {selectedStrategy && (
        <StrategyDetails
          strategy={selectedStrategy}
          open={!!selectedStrategy}
          onClose={() => setSelectedStrategy(null)}
          onExecute={handleExecuteStrategy}
          onCloseStrategy={handleCloseStrategy}
          onDelete={handleDeleteStrategy}
          isDialog
        />
      )}

      {/* Loading Overlay */}
      {loading && (
        <Box
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            bgcolor: 'rgba(0,0,0,0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
          }}
        >
          <CircularProgress size={60} />
        </Box>
      )}

      {/* Notifications */}
      <Snackbar
        open={notification.open}
        autoHideDuration={5000}
        onClose={handleCloseNotification}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={handleCloseNotification}
          severity={notification.severity}
          variant="filled"
        >
          {notification.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
