import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Chip,
  IconButton,
  Collapse,
  Alert,
  AlertTitle,
  Grid,
  Divider,
  CircularProgress,
  Tooltip
} from '@mui/material';
import {
  ExpandMore,
  ExpandLess,
  PlayArrow,
  Stop,
  Warning,
  CheckCircle,
  Error,
  Info,
  Refresh,
  Settings,
  Assessment,
  Sync as SyncIcon
} from '@mui/icons-material';
import HelpIcon from './help/HelpIcon';
import { useSocket } from '../hooks/useSocket';
import {
  getReconciliationStatus,
  getReconciliationV2Status,
  getTradingStatus,
  startTrading as apiStartTrading,
  stopTrading as apiStopTrading,
} from '../lib/api';
import api from '../utils/apiShim';

export default function TradingStatusPanel({ onNavigate, featureFlags = {} }) {
  const [status, setStatus] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reconStatus, setReconStatus] = useState(null);
  const socket = useSocket();
  const reconV2Enabled = Boolean(featureFlags?.reconciliation_v2);

  // Fetch trading status
  const fetchStatus = useCallback(async () => {
    try {
      const data = await getTradingStatus();
      if (data.success) {
        setStatus(data);
        setError(null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // Fetch reconciliation status
  const fetchReconStatus = useCallback(async () => {
    try {
      if (reconV2Enabled) {
        const data = await getReconciliationV2Status();
        setReconStatus(data);
      } else {
        const data = await getReconciliationStatus();
        setReconStatus(data);
      }
    } catch (err) {
      console.error('Failed to fetch reconciliation status:', err);
    }
  }, [reconV2Enabled]);

  // Auto-refresh reconciliation every 15 seconds
  useEffect(() => {
    fetchReconStatus();
    const interval = setInterval(fetchReconStatus, 15000);
    return () => clearInterval(interval);
  }, [fetchReconStatus]);

  useEffect(() => {
    if (!socket) return;

    const handleOrdersMemoryUpdate = () => {
      fetchStatus();
      fetchReconStatus();
    };

    socket.on('orders_memory_update', handleOrdersMemoryUpdate);
    socket.on('reconciliation_update', handleOrdersMemoryUpdate);

    return () => {
      socket.off('orders_memory_update', handleOrdersMemoryUpdate);
      socket.off('reconciliation_update', handleOrdersMemoryUpdate);
    };
  }, [socket, fetchStatus, fetchReconStatus]);

  // Handle start trading
  const handleStart = async (force = false) => {
    try {
      const response = await apiStartTrading(force);
      if (!response.success) {
        throw new Error(response.error || 'Failed to start trading');
      }
      fetchStatus();
    } catch (err) {
      setError(err.message);
    }
  };

  // Handle stop trading
  const handleStop = async (hardStop = false) => {
    try {
      const response = await apiStopTrading(hardStop);
      if (!response.success) {
        throw new Error(response.error || 'Failed to stop trading');
      }
      fetchStatus();
    } catch (err) {
      setError(err.message);
    }
  };

  // Handle blocker click - navigate to fix location
  const handleBlockerClick = (blocker) => {
    console.log('🔍 Blocker clicked:', blocker);
    console.log('🔍 Deep link:', blocker.deep_link);
    console.log('🔍 onNavigate function:', onNavigate);
    
    // Direct navigation based on blocker type
    if (blocker.id === 'gatekeeper_emergency_flag') {
      console.log('✅ Navigating to Emergency Controls tab (8)');
      if (onNavigate) {
        onNavigate('emergency_controls', 'emergency_status', null);
      }
    } else if (blocker.deep_link && onNavigate) {
      console.log('✅ Calling onNavigate with:', blocker.deep_link.tab, blocker.deep_link.section, blocker.deep_link.field);
      onNavigate(blocker.deep_link.tab, blocker.deep_link.section, blocker.deep_link.field);
    } else {
      console.log('❌ Navigation failed - missing deep_link or onNavigate');
    }
  };

  // Handle emergency actions - self-service controls
  const handleEmergencyAction = async (action) => {
    try {
      let endpoint = '';
      let confirmMessage = '';
      
      switch (action) {
        case 'clear_emergency_flag':
          endpoint = '/api/emergency/clear_flag';
          confirmMessage = 'Are you sure you want to clear the emergency stop flag? This will resume trading.';
          break;
        case 'reset_gatekeeper':
          endpoint = '/api/emergency/reset_gatekeeper';
          confirmMessage = 'Are you sure you want to reset the Safety Gatekeeper? This will clear all gatekeeper blocks.';
          break;
        case 'force_restart':
          endpoint = '/api/emergency/force_restart';
          confirmMessage = 'Are you sure you want to force restart the bot? This will stop and restart all bot processes.';
          break;
        default:
          throw new Error('Unknown emergency action');
      }
      
      if (window.confirm(confirmMessage)) {
        const response = await api.post(endpoint);
        if (response.data.success) {
          alert(`✅ ${action.replace('_', ' ')} completed successfully!`);
          fetchStatus(); // Refresh status
        } else {
          alert(`❌ ${action.replace('_', ' ')} failed: ${response.data.message}`);
        }
      }
    } catch (err) {
      alert(`❌ Error: ${err.message}`);
    }
  };

  const mismatchCount = useMemo(() => {
    if (!reconStatus) return 0;
    if (reconV2Enabled) {
      const counts = reconStatus?.report?.counts || {};
      return (counts.ghost || 0) + (counts.stray || 0) + (counts.diverged || 0);
    }
    const summaryCounters = reconStatus?.summary?.counters;
    return summaryCounters?.mismatched || 0;
  }, [reconStatus, reconV2Enabled]);

  const reconAvailable = useMemo(() => {
    if (reconV2Enabled) {
      return Boolean(reconStatus?.available && reconStatus?.report);
    }
    return Boolean(reconStatus);
  }, [reconStatus, reconV2Enabled]);

  const reconHasIssues = reconAvailable && mismatchCount > 0;

  // Get status color
  const getStatusColor = () => {
    if (!status) return 'grey';
    switch (status.status.trading_status) {
      case 'active':
        return '#4caf50'; // Green
      case 'blocked':
        return '#f44336'; // Red
      case 'bot_stopped':
        return '#9e9e9e'; // Gray
      default:
        return '#9e9e9e';
    }
  };

  // Get status icon
  const getStatusIcon = () => {
    if (!status) return <CircularProgress size={20} />;
    switch (status.status.trading_status) {
      case 'active':
        return <CheckCircle />;
      case 'blocked':
        return <Error />;
      case 'bot_stopped':
        return <Stop />;
      default:
        return <Info />;
    }
  };

  // Get status text with specific reason
  const getStatusText = () => {
    if (!status) return 'Loading...';
    
    switch (status.status.trading_status) {
      case 'active':
        // Show why trading is active
        if (status.status.total_blockers === 0) {
          return 'ACTIVE — All safety checks passed';
        } else {
          return 'ACTIVE — Blockers overridden by user';
        }
      
      case 'blocked':
        // Show specific blocking reason
        const criticalBlockers = status.blockers.filter(b => b.active && b.severity === 'critical');
        if (criticalBlockers.length > 0) {
          // Show the first critical blocker name
          const primaryBlocker = criticalBlockers[0];
          return `STOPPED — ${primaryBlocker.name}`;
        }
        return `STOPPED — ${status.status.total_blockers} issue${status.status.total_blockers > 1 ? 's' : ''} detected`;
      
      case 'bot_stopped':
        return 'BOT NOT RUNNING — Start bot to begin trading';
      
      default:
        return 'UNKNOWN STATUS';
    }
  };

  // Get detailed status context
  const getStatusContext = () => {
    if (!status) return null;
    
    switch (status.status.trading_status) {
      case 'active':
        if (status.status.total_blockers === 0) {
          return 'Safety Gatekeeper, Risk Manager, and Position Monitor all operational';
        } else {
          return `${status.status.total_blockers} blocker${status.status.total_blockers > 1 ? 's' : ''} present but trading enabled`;
        }
      
      case 'blocked':
        const criticalBlockers = status.blockers.filter(b => b.active && b.severity === 'critical');
        if (criticalBlockers.length > 0) {
          const primaryBlocker = criticalBlockers[0];
          return primaryBlocker.message || 'Click to view details';
        }
        return 'Multiple safety conditions preventing trade execution';
      
      case 'bot_stopped':
        return 'Main trading bot process is not active';
      
      default:
        return null;
    }
  };

  // Render collapsed view (always visible)
  const renderCollapsed = () => {
    const statusColor = getStatusColor();
    const statusIcon = getStatusIcon();
    const statusText = getStatusText();
    const statusContext = getStatusContext();

    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: { xs: 1.5, md: 2 },
          bgcolor: `rgba(${statusColor === '#4caf50' ? '76, 175, 80' : statusColor === '#f44336' ? '244, 67, 54' : '158, 158, 158'}, 0.1)`,
          borderBottom: `3px solid ${statusColor}`,
          flexWrap: { xs: 'wrap', lg: 'nowrap' },
          gap: { xs: 1, md: 2 }
        }}
      >
        <Box sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: { xs: 1, md: 2 },
          flex: { xs: '1 1 100%', lg: '1 1 auto' }
        }}>
          <Box sx={{ color: statusColor }}>
            {statusIcon}
          </Box>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
            <Typography 
              variant="h6" 
              fontWeight="bold"
              sx={{ fontSize: { xs: '0.95rem', sm: '1.1rem', md: '1.25rem' } }}
            >
              TRADING: {statusText}
            </Typography>
            {statusContext && (
              <Typography 
                variant="caption" 
                sx={{ 
                  fontSize: { xs: '0.7rem', md: '0.75rem' },
                  color: 'text.secondary',
                  fontStyle: 'italic'
                }}
              >
                {statusContext}
              </Typography>
            )}
          </Box>
          {status && (
            <>
              <Divider orientation="vertical" flexItem sx={{ display: { xs: 'none', md: 'block' } }} />
              <Box sx={{ 
                display: 'flex', 
                gap: 0.5,
                flexWrap: 'wrap'
              }}>
                <Chip
                  label={`${status.metrics.open_positions} Pos`}
                  size="small"
                  color="primary"
                  variant="outlined"
                  sx={{ fontSize: { xs: '0.65rem', md: '0.75rem' } }}
                />
                <Chip
                  label={`₹${status.metrics.total_pnl.toFixed(2)}`}
                  size="small"
                  color={status.metrics.total_pnl >= 0 ? 'success' : 'error'}
                  sx={{ fontSize: { xs: '0.65rem', md: '0.75rem' } }}
                />
                {status.status.total_blockers > 0 && (
                  <Chip
                    icon={<Warning sx={{ fontSize: { xs: '0.9rem', md: '1rem' } }} />}
                    label={`${status.status.total_blockers} Blockers`}
                    size="small"
                    color="warning"
                    sx={{ fontSize: { xs: '0.65rem', md: '0.75rem' } }}
                  />
                )}
                {reconAvailable ? (
                  reconHasIssues ? (
                    <Tooltip title="Click to view reconciliation details">
                      <Chip
                        icon={<SyncIcon sx={{ fontSize: { xs: '0.9rem', md: '1rem' } }} />}
                        label={`Recon: ❗${mismatchCount} issues`}
                        size="small"
                        color="error"
                        onClick={() => onNavigate && onNavigate('reconciliation', null, null)}
                        sx={{
                          fontSize: { xs: '0.65rem', md: '0.75rem' },
                          cursor: 'pointer'
                        }}
                      />
                    </Tooltip>
                  ) : (
                    <Tooltip title={reconV2Enabled ? 'Reconciliation snapshot in sync' : 'Reconciliation in sync'}>
                      <Chip
                        icon={<CheckCircle sx={{ fontSize: { xs: '0.9rem', md: '1rem' } }} />}
                        label="Recon: ✅ In sync"
                        size="small"
                        color="success"
                        variant="outlined"
                        sx={{ fontSize: { xs: '0.65rem', md: '0.75rem' } }}
                      />
                    </Tooltip>
                  )
                ) : (
                  <Chip
                    icon={<SyncIcon sx={{ fontSize: { xs: '0.9rem', md: '1rem' } }} />}
                    label="Recon: ⏳ Pending"
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: { xs: '0.65rem', md: '0.75rem' } }}
                  />
                )}
              </Box>
            </>
          )}
        </Box>

        <Box sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 1,
          flex: { xs: '0 0 auto', lg: '0 0 auto' }
        }}>
          {/* Removed unnecessary Stop/Start buttons - Trading Active panel handles this */}
          <IconButton 
            onClick={() => setExpanded(!expanded)} 
            size="small"
            sx={{ 
              display: { xs: 'inline-flex', lg: 'inline-flex' },
              minWidth: '40px',
              minHeight: '40px'
            }}
          >
            {expanded ? <ExpandLess /> : <ExpandMore />}
          </IconButton>
        </Box>
      </Box>
    );
  };

  // Render expanded view
  const renderExpanded = () => {
    if (!status) return null;

    return (
      <Collapse in={expanded}>
        <Box sx={{ padding: { xs: 2, md: 3 } }}>
          {/* Metrics Row */}
          <Grid container spacing={{ xs: 1, md: 2 }} sx={{ mb: { xs: 2, md: 3 } }}>
            <Grid item xs={6} md={3}>
              <Paper sx={{ p: { xs: 1.5, md: 2 }, bgcolor: 'rgba(33, 150, 243, 0.1)' }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: { xs: '0.65rem', md: '0.75rem' } }}>
                  Open Positions
                </Typography>
                <Typography variant="h4" sx={{ fontSize: { xs: '1.5rem', md: '2.125rem' } }}>
                  {status.metrics.open_positions}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={6} md={3}>
              <Paper sx={{ p: { xs: 1.5, md: 2 }, bgcolor: 'rgba(76, 175, 80, 0.1)' }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: { xs: '0.65rem', md: '0.75rem' } }}>
                  Pending Orders
                </Typography>
                <Typography variant="h4" sx={{ fontSize: { xs: '1.5rem', md: '2.125rem' } }}>
                  {status.metrics.pending_orders}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={6} md={3}>
              <Paper sx={{ p: { xs: 1.5, md: 2 }, bgcolor: status.metrics.total_pnl >= 0 ? 'rgba(76, 175, 80, 0.1)' : 'rgba(244, 67, 54, 0.1)' }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: { xs: '0.65rem', md: '0.75rem' } }}>
                  Total PnL
                </Typography>
                <Typography variant="h4" color={status.metrics.total_pnl >= 0 ? 'success.main' : 'error.main'} sx={{ fontSize: { xs: '1.5rem', md: '2.125rem' } }}>
                  ₹{status.metrics.total_pnl.toFixed(2)}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={6} md={3}>
              <Paper sx={{ p: { xs: 1.5, md: 2 }, bgcolor: 'rgba(158, 158, 158, 0.1)' }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: { xs: '0.65rem', md: '0.75rem' } }}>
                  Bot Status
                </Typography>
                <Typography variant="h6" sx={{ fontSize: { xs: '0.875rem', md: '1.25rem' } }}>
                  {status.status.bot_running ? '🟢 Running' : '🔴 Stopped'}
                </Typography>
              </Paper>
            </Grid>
          </Grid>

          {/* Blockers Section - Central Control Hub */}
          {status.status.total_blockers > 0 && (
            <Box sx={{ mb: { xs: 2, md: 3 } }}>
              <Typography variant="h6" gutterBottom sx={{ fontSize: { xs: '1rem', md: '1.25rem' } }}>
                🚫 Trading Blocked - {status.status.total_blockers} Issue{status.status.total_blockers > 1 ? 's' : ''} Found
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Review and fix these conditions to resume trading. Click any issue to navigate to the fix location.
              </Typography>
              {status.blockers
                .filter(b => b.active)
                .map((blocker, index) => {
                  // Generate actionable steps based on blocker category
                  const getActionSteps = (blocker) => {
                    if (blocker.category === 'SAFETY_GATEKEEPER') {
                      if (blocker.id === 'gatekeeper_execute_orders') {
                        return [
                          '1. Navigate to Configuration tab',
                          '2. Find EXECUTE_ORDERS setting',
                          '3. Change value from False to True',
                          '4. Save configuration',
                          '5. Trading will resume automatically'
                        ];
                      }
                    } else if (blocker.category === 'RISK_MANAGER') {
                      return [
                        '1. Review current risk metrics',
                        '2. Either reduce position sizes or adjust risk limits',
                        '3. Wait for risk levels to normalize',
                        '4. Trading will resume when safe'
                      ];
                    } else if (blocker.category === 'POSITION_MONITOR') {
                      return [
                        '1. Add more margin to your account',
                        '2. Or close some positions to reduce risk',
                        '3. Wait for liquidation distance to increase',
                        '4. Trading will resume when safe distance restored'
                      ];
                    } else if (blocker.category === 'EXCHANGE_CONNECTION') {
                      return [
                        '1. Check your internet connection',
                        '2. Verify API keys are valid',
                        '3. Check exchange status page',
                        '4. Restart bot if connection persists'
                      ];
                    }
                    return ['Click to navigate to fix location'];
                  };

                  const actionSteps = getActionSteps(blocker);

                  return (
                    <Alert
                      key={index}
                      severity={blocker.severity === 'critical' ? 'error' : blocker.severity === 'warning' ? 'warning' : 'info'}
                      sx={{ 
                        mb: 2, 
                        cursor: 'pointer',
                        '&:hover': {
                          transform: 'translateY(-1px)',
                          boxShadow: 2
                        },
                        transition: 'all 0.2s ease-in-out'
                      }}
                      onClick={() => handleBlockerClick(blocker)}
                      action={
                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                          <Button
                            variant="contained"
                            color="error"
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleBlockerClick(blocker);
                            }}
                            sx={{ 
                              minWidth: 'auto',
                              px: 2,
                              py: 0.5,
                              fontSize: '0.75rem',
                              fontWeight: 'bold'
                            }}
                          >
                            EMERGENCY CONTROLS
                          </Button>
                          <Tooltip title="Click to navigate to fix location">
                            <IconButton size="small" color="inherit">
                              <Settings />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      }
                    >
                      <AlertTitle sx={{ fontWeight: 'bold', fontSize: '1rem' }}>
                        {blocker.severity === 'critical' ? '🚨' : '⚠️'} {blocker.name}
                      </AlertTitle>
                      
                      {/* Problem Description */}
                      <Typography variant="body2" sx={{ mb: 1.5, fontWeight: 500 }}>
                        <strong>Problem:</strong> {blocker.message}
                      </Typography>
                      
                      {/* How It Stopped Trading */}
                      <Typography variant="body2" sx={{ mb: 1.5, color: 'error.main', fontStyle: 'italic' }}>
                        <strong>How it stopped trading:</strong> {blocker.category === 'SAFETY_GATEKEEPER' 
                          ? 'Safety Gatekeeper intercepted all trade execution requests'
                          : blocker.category === 'RISK_MANAGER'
                          ? 'Risk Manager blocked new positions due to high risk'
                          : blocker.category === 'POSITION_MONITOR'
                          ? 'Position Monitor blocked trading to prevent liquidation'
                          : blocker.category === 'EXCHANGE_CONNECTION'
                          ? 'Exchange connection issues prevent order placement'
                          : 'Bot safety system blocked trade execution'
                        }
                      </Typography>
                      
                      {/* Action Steps */}
                      <Box sx={{ 
                        bgcolor: 'rgba(255, 255, 255, 0.05)', 
                        p: 1.5, 
                        borderRadius: 1,
                        border: '1px solid rgba(255, 255, 255, 0.1)'
                      }}>
                        <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block', mb: 1, color: 'success.main' }}>
                          ✅ STEPS TO RESUME TRADING:
                        </Typography>
                        {actionSteps.map((step, idx) => (
                          <Typography 
                            key={idx} 
                            variant="caption" 
                            display="block" 
                            sx={{ 
                              fontSize: '0.75rem',
                              mb: 0.5,
                              pl: 1
                            }}
                          >
                            {step}
                          </Typography>
                        ))}
                      </Box>
                      
                      <Typography variant="caption" display="block" sx={{ mt: 1.5, fontWeight: 'bold', color: 'primary.main' }}>
                        📂 Category: {blocker.category} | 🖱️ 
                        <Button
                          variant="text"
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleBlockerClick(blocker);
                          }}
                          sx={{ 
                            minWidth: 'auto',
                            p: 0,
                            fontSize: 'inherit',
                            fontWeight: 'bold',
                            color: 'primary.main',
                            textDecoration: 'underline',
                            '&:hover': {
                              backgroundColor: 'transparent',
                              textDecoration: 'underline'
                            }
                          }}
                        >
                          Click here to navigate to Emergency Controls
                        </Button>
                      </Typography>
                    </Alert>
                  );
                })}
            </Box>
          )}

          {/* No Blockers */}
          {status.status.total_blockers === 0 && (
            <Alert severity="success" sx={{ mb: 3 }}>
              <AlertTitle>✅ All Systems Healthy</AlertTitle>
              All safety systems are operational. Trading is allowed.
            </Alert>
          )}

          {/* Emergency Controls - Self-Service */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ fontSize: { xs: '1rem', md: '1.25rem' } }}>
              🛠️ Emergency Controls - Self-Service
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Use these controls to diagnose and fix issues independently without external help.
            </Typography>
            
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Paper sx={{ p: 2, bgcolor: 'rgba(255, 193, 7, 0.1)', border: '1px solid rgba(255, 193, 7, 0.3)' }}>
                  <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold' }}>
                    🔍 Diagnostic Tools
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<Refresh />}
                      onClick={fetchStatus}
                    >
                      Force Refresh Status
                    </Button>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<Settings />}
                      onClick={() => window.open('/api/trading_status', '_blank')}
                    >
                      View Raw API
                    </Button>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<Assessment />}
                      onClick={() => window.open('/api/bot/status', '_blank')}
                    >
                      Bot Status API
                    </Button>
                  </Box>
                </Paper>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <Paper sx={{ p: 2, bgcolor: 'rgba(244, 67, 54, 0.1)', border: '1px solid rgba(244, 67, 54, 0.3)' }}>
                  <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold' }}>
                    🚨 Emergency Actions
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                    <Button
                      variant="outlined"
                      color="warning"
                      size="small"
                      data-action-id="emergency.clear-flag"
                      onClick={() => handleEmergencyAction('clear_emergency_flag')}
                    >
                      Clear Emergency Flag
                    </Button>
                    <HelpIcon actionId="emergency.clear-flag" size="small" />
                    
                    <Button
                      variant="outlined"
                      color="warning"
                      size="small"
                      data-action-id="emergency.reset-gatekeeper"
                      onClick={() => handleEmergencyAction('reset_gatekeeper')}
                    >
                      Reset Gatekeeper
                    </Button>
                    <HelpIcon actionId="emergency.reset-gatekeeper" size="small" />
                    
                    <Button
                      variant="outlined"
                      color="error"
                      size="small"
                      data-action-id="emergency.force-restart"
                      onClick={() => handleEmergencyAction('force_restart')}
                    >
                      Force Restart Bot
                    </Button>
                    <HelpIcon actionId="emergency.force-restart" size="small" />
                  </Box>
                </Paper>
              </Grid>
            </Grid>
          </Box>

          {/* Action Buttons - Navigation */}
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={fetchStatus}
            >
              Refresh Status
            </Button>
            <Button
              variant="outlined"
              startIcon={<Assessment />}
              onClick={() => onNavigate && onNavigate('monitoring')}
            >
              View Full Dashboard
            </Button>
          </Box>
        </Box>
      </Collapse>
    );
  };

  return (
    <Paper
      elevation={3}
      sx={{
        width: '100%',
        borderRadius: 2,
        overflow: 'auto',
        mb: 2
      }}
    >
      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {renderCollapsed()}
      {renderExpanded()}
    </Paper>
  );
}
