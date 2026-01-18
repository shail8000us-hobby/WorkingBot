import React, { useMemo, useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Alert,
  AlertTitle,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Card,
  CardContent,
  Grid,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  FormControlLabel,
  Switch,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  CircularProgress,
  LinearProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Snackbar,
  Link,
} from '@mui/material';
import {
  Build as BuildIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  PlayArrow as PlayArrowIcon,
  Refresh as RefreshIcon,
  Build as AutoFixIcon,
  Settings as SettingsIcon,
  Security as SecurityIcon,
  Psychology as PsychologyIcon,
  ExpandMore as ExpandMoreIcon,
  Close as CloseIcon,
  Help as HelpIcon,
  CheckCircleOutline as CheckIcon,
  Cancel as CancelIcon,
  RestartAlt as RestartIcon,
  Tune as TuneIcon,
  Search as ScanIcon,
} from '@mui/icons-material';
import api from '../utils/apiShim';

/**
 * Enhanced Error Resolution Panel
 * Provides step-by-step guidance and auto-fix capabilities for common startup errors
 */
const AdvancedErrorResolutionPanel = ({ errors, onErrorUpdate, onStatsUpdate }) => {
  const [activeStep, setActiveStep] = useState(0);
  const [resolutionProgress, setResolutionProgress] = useState({});
  const [showAutoFixDialog, setShowAutoFixDialog] = useState(false);
  const [selectedErrors, setSelectedErrors] = useState([]);
  const [autoFixResult, setAutoFixResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState({ open: false, message: '', severity: 'info' });

  // Filter for startup-related errors
  const startupErrors = errors.filter(
    (error) =>
      error.code.startsWith('UNKNOWN_TRADING') ||
      error.code.includes('CONFIG') ||
      error.code.includes('ORDER') ||
      error.message_raw.includes('Safety gatekeeper blocked') ||
      error.message_raw.includes('CONFIGURATION CHANGES DETECTED')
  );

  const errorCategories = {
    'Safety Gatekeeper Blocks': startupErrors.filter((e) =>
      e.message_raw.includes('Safety gatekeeper blocked')
    ),
    'Configuration Issues': startupErrors.filter(
      (e) => e.message_raw.includes('CONFIGURATION CHANGES DETECTED') || e.code.includes('CONFIG')
    ),
    'General Trading Issues': startupErrors.filter((e) => e.code === 'UNKNOWN_TRADING_GENERAL'),
  };

  const resolutionSteps = [
    {
      label: 'Identify Issues',
      description: 'Review detected startup problems',
      icon: <PsychologyIcon />,
    },
    {
      label: 'Auto-Fix Common Issues',
      description: 'Automatically resolve known problems',
      icon: <AutoFixIcon />,
    },
    {
      label: 'Manual Configuration',
      description: 'Adjust settings if needed',
      icon: <SettingsIcon />,
    },
    {
      label: 'Verify Resolution',
      description: 'Confirm all issues are resolved',
      icon: <CheckCircleIcon />,
    },
  ];

  const commonFixes = {
    UNKNOWN_TRADING_ORDER: {
      title: 'Safety Gatekeeper Blocks',
      description: 'Orders are being blocked by safety systems',
      autoFix: true,
      fixSteps: [
        'Check current safety gatekeeper status',
        'Review margin utilization limits',
        'Verify order confirmation guard status',
        'Adjust safety parameters if needed',
      ],
      actions: [
        {
          id: 'check_gatekeeper_status',
          title: 'Check Gatekeeper Status',
          description: 'View current safety gatekeeper configuration',
          risk: 'low',
          endpoint: '/api/robustness/gatekeeper/status',
        },
        {
          id: 'check_margin_limits',
          title: 'Check Margin Limits',
          description: 'Review current margin utilization',
          risk: 'low',
          endpoint: '/api/robustness/loss-limits',
        },
        {
          id: 'reset_safety_limits',
          title: 'Reset Safety Limits',
          description: 'Reset safety limits to default values',
          risk: 'medium',
          endpoint: '/api/robustness/reset-safety-limits',
        },
      ],
    },
    UNKNOWN_TRADING_CONFIG: {
      title: 'Configuration Changes',
      description: 'Bot detected configuration changes during startup',
      autoFix: true,
      fixSteps: [
        'Verify configuration file integrity',
        'Check for conflicting settings',
        'Apply configuration changes',
        'Restart bot with new settings',
      ],
      actions: [
        {
          id: 'verify_config',
          title: 'Verify Configuration',
          description: 'Check configuration file for issues',
          risk: 'low',
          endpoint: '/api/config/verify',
        },
        {
          id: 'apply_config_changes',
          title: 'Apply Configuration Changes',
          description: 'Apply pending configuration changes',
          risk: 'low',
          endpoint: '/api/config/apply',
        },
        {
          id: 'restart_bot',
          title: 'Restart Bot',
          description: 'Restart bot with updated configuration',
          risk: 'medium',
          endpoint: '/api/bot/restart',
        },
      ],
    },
    UNKNOWN_TRADING_GENERAL: {
      title: 'General Trading Issues',
      description: 'Unclassified trading-related warnings',
      autoFix: false,
      fixSteps: [
        'Review log messages for details',
        'Check system status',
        'Verify trading permissions',
        'Clear false positive errors',
      ],
      actions: [
        {
          id: 'review_logs',
          title: 'Review Recent Logs',
          description: 'Check recent bot logs for details',
          risk: 'low',
          endpoint: '/api/logs/recent',
        },
        {
          id: 'check_system_status',
          title: 'Check System Status',
          description: 'Verify overall system health',
          risk: 'low',
          endpoint: '/api/system/status',
        },
        {
          id: 'mark_as_resolved',
          title: 'Mark as Resolved',
          description: 'Mark these as false positive errors',
          risk: 'low',
          endpoint: '/api/errors/resolve',
        },
      ],
    },
  };

  const showNotification = (message, severity = 'info') => {
    setNotification({ open: true, message, severity });
  };

  const handleAutoFix = async (errorCode) => {
    const fix = commonFixes[errorCode];
    if (!fix || !fix.autoFix) return;

    setLoading(true);
    try {
      // Execute auto-fix actions
      for (const action of fix.actions) {
        if (action.risk === 'low') {
          await executeAction(action, errorCode);
        }
      }

      showNotification(`Auto-fix completed for ${fix.title}`, 'success');
      onErrorUpdate();
      onStatsUpdate();
    } catch (error) {
      showNotification(`Auto-fix failed: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const executeAction = async (action, errorCode) => {
    try {
      let response;

      switch (action.id) {
        case 'check_gatekeeper_status':
          response = await api.get(action.endpoint);
          console.log('Gatekeeper Status:', response.data);
          break;

        case 'check_margin_limits':
          response = await api.get(action.endpoint);
          console.log('Margin Limits:', response.data);
          break;

        case 'verify_config':
          response = await api.get(action.endpoint);
          console.log('Config Verification:', response.data);
          break;

        case 'apply_config_changes':
          response = await api.post(action.endpoint);
          console.log('Config Applied:', response.data);
          break;

        case 'mark_as_resolved':
          // Mark all errors of this type as resolved
          const errorsToResolve = errors.filter((e) => e.code === errorCode);
          for (const error of errorsToResolve) {
            await api.post(action.endpoint, {
              error_id: error.id,
              user: 'auto-fix-system',
              notes: `Auto-resolved: ${action.description}`,
            });
          }
          break;

        default:
          console.log(`Action ${action.id} not implemented yet`);
      }

      return response?.data || { success: true };
    } catch (error) {
      console.error(`Failed to execute ${action.id}:`, error);
      throw error;
    }
  };

  const handleBulkResolve = async () => {
    setLoading(true);
    try {
      const resolvePromises = selectedErrors.map((error) =>
        api.post('/api/errors/resolve', {
          error_id: error.id,
          user: 'webui-user',
          notes: 'Bulk resolved via Error Resolution Panel',
        })
      );

      await Promise.all(resolvePromises);
      showNotification(`Resolved ${selectedErrors.length} errors`, 'success');
      setSelectedErrors([]);
      onErrorUpdate();
      onStatsUpdate();
    } catch (error) {
      showNotification(`Failed to resolve errors: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const getErrorSeverityIcon = (severity) => {
    switch (severity) {
      case 'critical':
        return <ErrorIcon color="error" />;
      case 'high':
        return <WarningIcon color="warning" />;
      case 'medium':
        return <InfoIcon color="info" />;
      default:
        return <InfoIcon color="action" />;
    }
  };

  const getErrorSeverityColor = (severity) => {
    switch (severity) {
      case 'critical':
        return 'error';
      case 'high':
        return 'warning';
      case 'medium':
        return 'info';
      default:
        return 'default';
    }
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <BuildIcon color="primary" sx={{ fontSize: 32 }} />
          <Box>
            <Typography variant="h5" fontWeight={600}>
              Error Resolution Center
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Fix startup issues and get your bot running smoothly
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => {
              onErrorUpdate();
              onStatsUpdate();
            }}
          >
            Refresh
          </Button>
          {selectedErrors.length > 0 && (
            <Button
              variant="contained"
              color="success"
              startIcon={<CheckCircleIcon />}
              onClick={handleBulkResolve}
              disabled={loading}
            >
              Resolve Selected ({selectedErrors.length})
            </Button>
          )}
        </Box>
      </Box>

      {/* Summary Alert */}
      <Alert severity={startupErrors.length > 0 ? 'warning' : 'success'} sx={{ mb: 3 }}>
        <AlertTitle>
          {startupErrors.length > 0
            ? `${startupErrors.length} Startup Issue${startupErrors.length > 1 ? 's' : ''} Detected`
            : 'All Systems Running Smoothly'}
        </AlertTitle>
        {startupErrors.length > 0 ? (
          <Typography variant="body2">
            We've detected some issues that commonly occur during bot startup. Use the steps below
            to resolve them quickly.
          </Typography>
        ) : (
          <Typography variant="body2">
            No startup issues detected. Your bot is running normally.
          </Typography>
        )}
      </Alert>

      {startupErrors.length > 0 && (
        <>
          {/* Resolution Steps */}
          <Box sx={{ mb: 4 }}>
            <Typography variant="h6" gutterBottom>
              Resolution Steps
            </Typography>
            <Stepper activeStep={activeStep} orientation="vertical">
              {resolutionSteps.map((step, index) => (
                <Step key={step.label}>
                  <StepLabel
                    icon={step.icon}
                    optional={
                      index === resolutionSteps.length - 1 ? (
                        <Typography variant="caption">Last step</Typography>
                      ) : null
                    }
                  >
                    {step.label}
                  </StepLabel>
                  <StepContent>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      {step.description}
                    </Typography>
                    <Box sx={{ mb: 2 }}>
                      <Button
                        variant="contained"
                        onClick={() => setActiveStep(index + 1)}
                        sx={{ mt: 1, mr: 1 }}
                      >
                        {index === resolutionSteps.length - 1 ? 'Finish' : 'Continue'}
                      </Button>
                      {index > 0 && (
                        <Button onClick={() => setActiveStep(index - 1)} sx={{ mt: 1, mr: 1 }}>
                          Back
                        </Button>
                      )}
                    </Box>
                  </StepContent>
                </Step>
              ))}
            </Stepper>
          </Box>

          <Divider sx={{ my: 3 }} />

          {/* Error Categories */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Error Categories
            </Typography>

            {Object.entries(errorCategories).map(
              ([category, categoryErrors]) =>
                categoryErrors.length > 0 && (
                  <Accordion key={category} sx={{ mb: 2 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                        {getErrorSeverityIcon('medium')}
                        <Typography variant="subtitle1" fontWeight={500}>
                          {category}
                        </Typography>
                        <Chip
                          label={`${categoryErrors.length} issue${categoryErrors.length > 1 ? 's' : ''}`}
                          size="small"
                          color="info"
                        />
                      </Box>
                    </AccordionSummary>

                    <AccordionDetails>
                      <Grid container spacing={2}>
                        {categoryErrors.map((error) => {
                          const fix = commonFixes[error.code];
                          return (
                            <Grid item xs={12} key={error.id}>
                              <Card variant="outlined">
                                <CardContent>
                                  <Box
                                    sx={{
                                      display: 'flex',
                                      justifyContent: 'space-between',
                                      alignItems: 'flex-start',
                                      mb: 2,
                                    }}
                                  >
                                    <Box sx={{ flexGrow: 1 }}>
                                      <Box
                                        sx={{
                                          display: 'flex',
                                          alignItems: 'center',
                                          gap: 1,
                                          mb: 1,
                                        }}
                                      >
                                        <Typography variant="subtitle2" fontWeight={600}>
                                          {error.code}
                                        </Typography>
                                        <Chip
                                          label={error.severity}
                                          size="small"
                                          color={getErrorSeverityColor(error.severity)}
                                          sx={{ textTransform: 'uppercase' }}
                                        />
                                        <Chip
                                          label={`${error.occurrence_count} occurrence${error.occurrence_count > 1 ? 's' : ''}`}
                                          size="small"
                                          variant="outlined"
                                        />
                                      </Box>

                                      <Typography
                                        variant="body2"
                                        color="text.secondary"
                                        sx={{ mb: 1 }}
                                      >
                                        {error.message_raw}
                                      </Typography>

                                      <Typography variant="caption" color="text.secondary">
                                        First seen: {formatTimestamp(error.first_seen)} | Last seen:{' '}
                                        {formatTimestamp(error.last_seen)}
                                      </Typography>
                                    </Box>

                                    <Box sx={{ display: 'flex', gap: 1, ml: 2 }}>
                                      <FormControlLabel
                                        control={
                                          <Switch
                                            checked={selectedErrors.some((e) => e.id === error.id)}
                                            onChange={(e) => {
                                              if (e.target.checked) {
                                                setSelectedErrors([...selectedErrors, error]);
                                              } else {
                                                setSelectedErrors(
                                                  selectedErrors.filter((e) => e.id !== error.id)
                                                );
                                              }
                                            }}
                                          />
                                        }
                                        label="Select"
                                        sx={{ m: 0 }}
                                      />
                                    </Box>
                                  </Box>

                                  {fix && (
                                    <>
                                      <Divider sx={{ my: 2 }} />

                                      <Typography variant="subtitle2" gutterBottom>
                                        {fix.title}
                                      </Typography>
                                      <Typography
                                        variant="body2"
                                        color="text.secondary"
                                        sx={{ mb: 2 }}
                                      >
                                        {fix.description}
                                      </Typography>

                                      <Box sx={{ mb: 2 }}>
                                        <Typography variant="subtitle2" gutterBottom>
                                          Fix Steps:
                                        </Typography>
                                        <List dense>
                                          {fix.fixSteps.map((step, idx) => (
                                            <ListItem key={idx} sx={{ py: 0.5 }}>
                                              <ListItemIcon sx={{ minWidth: 32 }}>
                                                <Typography variant="body2" color="primary">
                                                  {idx + 1}.
                                                </Typography>
                                              </ListItemIcon>
                                              <ListItemText primary={step} />
                                            </ListItem>
                                          ))}
                                        </List>
                                      </Box>

                                      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                        {fix.autoFix && (
                                          <Button
                                            size="small"
                                            variant="contained"
                                            startIcon={<AutoFixIcon />}
                                            onClick={() => handleAutoFix(error.code)}
                                            disabled={loading}
                                            color="primary"
                                          >
                                            Auto-Fix
                                          </Button>
                                        )}

                                        <Button
                                          size="small"
                                          variant="outlined"
                                          startIcon={<CheckCircleIcon />}
                                          onClick={() => {
                                            api
                                              .post('/api/errors/resolve', {
                                                error_id: error.id,
                                                user: 'webui-user',
                                                notes: 'Resolved via Error Resolution Panel',
                                              })
                                              .then(() => {
                                                showNotification(
                                                  'Error resolved successfully',
                                                  'success'
                                                );
                                                onErrorUpdate();
                                                onStatsUpdate();
                                              })
                                              .catch((err) => {
                                                showNotification(
                                                  `Failed to resolve: ${err.message}`,
                                                  'error'
                                                );
                                              });
                                          }}
                                        >
                                          Mark Resolved
                                        </Button>

                                        <Button
                                          size="small"
                                          variant="outlined"
                                          startIcon={<HelpIcon />}
                                          onClick={() => {
                                            // Open help dialog or navigate to documentation
                                            showNotification(
                                              'Help documentation coming soon',
                                              'info'
                                            );
                                          }}
                                        >
                                          Get Help
                                        </Button>
                                      </Box>
                                    </>
                                  )}
                                </CardContent>
                              </Card>
                            </Grid>
                          );
                        })}
                      </Grid>
                    </AccordionDetails>
                  </Accordion>
                )
            )}
          </Box>

          {/* Quick Actions */}
          <Box sx={{ mt: 4 }}>
            <Typography variant="h6" gutterBottom>
              Quick Actions
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ textAlign: 'center' }}>
                    <AutoFixIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
                    <Typography variant="subtitle2" gutterBottom>
                      Auto-Fix All
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      Automatically resolve common startup issues
                    </Typography>
                    <Button
                      variant="contained"
                      fullWidth
                      startIcon={<AutoFixIcon />}
                      onClick={() => setShowAutoFixDialog(true)}
                    >
                      Run Auto-Fix
                    </Button>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ textAlign: 'center' }}>
                    <SettingsIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
                    <Typography variant="subtitle2" gutterBottom>
                      Check Settings
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      Review bot configuration and safety limits
                    </Typography>
                    <Button
                      variant="outlined"
                      fullWidth
                      startIcon={<SettingsIcon />}
                      onClick={() => {
                        // Navigate to config panel
                        showNotification('Opening configuration panel...', 'info');
                      }}
                    >
                      Open Config
                    </Button>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ textAlign: 'center' }}>
                    <SecurityIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
                    <Typography variant="subtitle2" gutterBottom>
                      Safety Check
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      Verify safety gatekeeper status
                    </Typography>
                    <Button
                      variant="outlined"
                      fullWidth
                      startIcon={<SecurityIcon />}
                      onClick={async () => {
                        try {
                          const response = await api.get('/api/robustness/gatekeeper/status');
                          showNotification('Safety gatekeeper status checked', 'success');
                        } catch (error) {
                          showNotification(`Safety check failed: ${error.message}`, 'error');
                        }
                      }}
                    >
                      Check Safety
                    </Button>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ textAlign: 'center' }}>
                    <RestartIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
                    <Typography variant="subtitle2" gutterBottom>
                      Restart Bot
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      Restart bot with current configuration
                    </Typography>
                    <Button
                      variant="outlined"
                      fullWidth
                      startIcon={<RestartIcon />}
                      onClick={() => {
                        if (
                          window.confirm(
                            'Are you sure you want to restart the bot? This will stop all current trading.'
                          )
                        ) {
                          api
                            .post('/api/bot/restart')
                            .then(() => {
                              showNotification('Bot restart initiated', 'success');
                            })
                            .catch((err) => {
                              showNotification(`Restart failed: ${err.message}`, 'error');
                            });
                        }
                      }}
                    >
                      Restart Bot
                    </Button>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Box>
        </>
      )}

      {/* Auto-Fix Dialog */}
      <Dialog
        open={showAutoFixDialog}
        onClose={() => setShowAutoFixDialog(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <AutoFixIcon color="primary" />
            <Typography variant="h6">Auto-Fix Startup Issues</Typography>
          </Box>
        </DialogTitle>

        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            This will automatically attempt to resolve common startup issues. Safe operations will
            be performed automatically, while risky operations require confirmation.
          </Typography>

          <List>
            {Object.entries(commonFixes).map(([code, fix]) => {
              const errorCount = startupErrors.filter((e) => e.code === code).length;
              if (errorCount === 0) return null;

              return (
                <ListItem key={code} sx={{ px: 0 }}>
                  <ListItemIcon>
                    {fix.autoFix ? <CheckIcon color="success" /> : <CancelIcon color="disabled" />}
                  </ListItemIcon>
                  <ListItemText
                    primary={`${fix.title} (${errorCount} issue${errorCount > 1 ? 's' : ''})`}
                    secondary={fix.description}
                  />
                </ListItem>
              );
            })}
          </List>
        </DialogContent>

        <DialogActions>
          <Button onClick={() => setShowAutoFixDialog(false)}>Cancel</Button>
          <Button
            variant="contained"
            startIcon={<AutoFixIcon />}
            onClick={async () => {
              setShowAutoFixDialog(false);
              setLoading(true);

              try {
                for (const [code, fix] of Object.entries(commonFixes)) {
                  if (fix.autoFix) {
                    await handleAutoFix(code);
                  }
                }
                showNotification('Auto-fix completed successfully', 'success');
              } catch (error) {
                showNotification(`Auto-fix failed: ${error.message}`, 'error');
              } finally {
                setLoading(false);
              }
            }}
            disabled={loading}
          >
            {loading ? <CircularProgress size={20} /> : 'Run Auto-Fix'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Notification Snackbar */}
      <Snackbar
        open={notification.open}
        autoHideDuration={6000}
        onClose={() => setNotification({ ...notification, open: false })}
        message={notification.message}
        severity={notification.severity}
      />
    </Paper>
  );
};

const SIMPLE_DEFAULT_STATS = {
  by_severity: { critical: 0, high: 0, medium: 0, low: 0 },
  by_status: { open: 0, acknowledged: 0, resolved: 0 },
  total: 0,
};

const deriveSimpleStatus = (stats) => {
  const safeStats = stats || SIMPLE_DEFAULT_STATS;
  const openCount = (safeStats.by_status?.open || 0) + (safeStats.by_status?.acknowledged || 0);
  const hasCritical = (safeStats.by_severity?.critical || 0) > 0;
  const hasHigh = (safeStats.by_severity?.high || 0) > 0;

  const getStatusColor = () => {
    if (hasCritical) return 'error.dark';
    if (hasHigh) return 'warning.dark';
    return 'success.dark';
  };

  const getStatusIcon = () => {
    if (hasCritical) return <ErrorIcon sx={{ fontSize: 28 }} />;
    if (hasHigh) return <WarningIcon sx={{ fontSize: 28 }} />;
    return <CheckCircleIcon sx={{ fontSize: 28 }} />;
  };

  const getStatusText = () => {
    if (hasCritical) return `${safeStats.by_severity.critical} Critical Issues`;
    if (hasHigh) return `${safeStats.by_severity.high} High Priority Issues`;
    if (openCount > 0) return `${openCount} Open Issues`;
    return 'Everything Okay :))';
  };

  return {
    openCount,
    hasCritical,
    hasHigh,
    hasErrors: openCount > 0,
    getStatusColor,
    getStatusIcon,
    getStatusText,
  };
};

const SimpleErrorResolutionPanel = ({ errors = [], statistics, onErrorUpdate, onStatsUpdate }) => {
  const [showAll, setShowAll] = useState(false);
  const [resolvingErrors, setResolvingErrors] = useState({});
  const [scanning, setScanning] = useState(false);

  const meta = deriveSimpleStatus(statistics);

  const startupErrors = useMemo(
    () =>
      errors.filter(
        (error) =>
          error.code?.includes('SAFETY_GATEKEEPER') ||
          error.code?.includes('CONFIG') ||
          error.code?.includes('LOG_FORMATTING')
      ),
    [errors]
  );

  const counts = useMemo(
    () => ({
      gatekeeper: startupErrors.filter((e) => e.code?.includes('SAFETY_GATEKEEPER')).length,
      config: startupErrors.filter((e) => e.code?.includes('CONFIG')).length,
      falsePositive: startupErrors.filter((e) => e.code?.includes('LOG_FORMATTING')).length,
    }),
    [startupErrors]
  );

  const handleRefresh = async () => {
    if (onErrorUpdate) {
      await onErrorUpdate();
    }
    if (onStatsUpdate) {
      await onStatsUpdate();
    }
  };

  const markAsResolved = async (errorGroup) => {
    const ids = errorGroup?.ids || (errorGroup?.id ? [errorGroup.id] : []);
    if (ids.length === 0) {
      return;
    }

    const key = errorGroup.aggregation_key || ids[0];
    setResolvingErrors((prev) => ({ ...prev, [key]: true }));

    try {
      for (const errorId of ids) {
        const { data } = await api.post(`/api/errors/resolve`, {
          error_id: errorId,
          user: 'webui-user',
          notes: 'Manually resolved via simple panel',
        });
        if (!data.success) {
          console.error('Failed to resolve:', data.error);
          alert(`Failed to resolve error: ${data.error}`);
          break;
        }
      }

      await handleRefresh();
    } catch (error) {
      console.error('Error resolving:', error);
      alert('Failed to resolve error. Please try again.');
    } finally {
      setResolvingErrors((prev) => ({ ...prev, [key]: false }));
    }
  };

  const scanForErrors = async () => {
    setScanning(true);

    try {
      const { data } = await api.post('/api/errors/scan');

      if (data.success) {
        if (data.found > 0) {
          alert(`✅ Scan complete: Found ${data.found} new error${data.found > 1 ? 's' : ''}`);
        } else {
          alert('✅ Scan complete: No new errors found');
        }
        await handleRefresh();
      } else {
        console.error('Scan failed:', data.error);
        alert(`Scan failed: ${data.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error scanning:', error);
      alert('Failed to scan for errors. Please try again.');
    } finally {
      setScanning(false);
    }
  };

  return (
    <Paper
      elevation={meta.hasErrors ? 6 : 3}
      sx={{
        mt: 3,
        mb: 2,
        overflow: 'hidden',
        borderTop: 3,
        borderColor: meta.getStatusColor(),
        transition: 'all 0.3s',
      }}
    >
      <Box
        sx={{
          p: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          bgcolor: meta.hasErrors ? 'rgba(255, 0, 0, 0.05)' : 'rgba(0, 255, 0, 0.05)',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box
            sx={{
              p: 1,
              borderRadius: 2,
              bgcolor: meta.getStatusColor(),
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {meta.getStatusIcon()}
          </Box>

          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <PsychologyIcon sx={{ color: 'primary.main', fontSize: 20 }} />
              <Typography variant="h6" fontWeight={600}>
                Error Intelligence
              </Typography>
            </Box>
            <Typography
              variant="body2"
              color={meta.hasErrors ? 'error.main' : 'success.main'}
              fontWeight={500}
            >
              {meta.getStatusText()}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Button
            variant="outlined"
            size="small"
            color="primary"
            startIcon={scanning ? <CircularProgress size={16} /> : <ScanIcon />}
            onClick={scanForErrors}
            disabled={scanning}
            sx={{ minWidth: 150 }}
          >
            {scanning ? 'Scanning...' : 'Scan for Errors'}
          </Button>

          {meta.hasCritical && (
            <Chip
              icon={<ErrorIcon />}
              label={`${statistics?.by_severity?.critical || 0} Critical`}
              color="error"
              size="small"
              sx={{ fontWeight: 600 }}
            />
          )}
          {meta.hasHigh && (
            <Chip
              icon={<WarningIcon />}
              label={`${statistics?.by_severity?.high || 0} High`}
              color="warning"
              size="small"
              sx={{ fontWeight: 600 }}
            />
          )}
          {(statistics?.by_severity?.medium || 0) > 0 && (
            <Chip label={`${statistics.by_severity.medium} Medium`} color="info" size="small" />
          )}
        </Box>
      </Box>

      {meta.hasErrors && errors.length > 0 && (
        <Box sx={{ p: 2, bgcolor: 'background.default' }}>
          {meta.hasCritical && (
            <Alert severity="error" sx={{ mb: 2 }} icon={<ErrorIcon />}>
              <Typography variant="body2" fontWeight={500}>
                🚨 {statistics?.by_severity?.critical || 0} critical{' '}
                {(statistics?.by_severity?.critical || 0) === 1 ? 'issue' : 'issues'} detected -
                Immediate attention required!
              </Typography>
            </Alert>
          )}

          <Divider sx={{ my: 2 }} />

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Chip label={`Gatekeeper: ${counts.gatekeeper}`} color="warning" variant="outlined" />
            <Chip label={`Config: ${counts.config}`} color="info" variant="outlined" />
            <Chip
              label={`False Positives: ${counts.falsePositive}`}
              color="success"
              variant="outlined"
            />
          </Box>

          <Divider sx={{ my: 2 }} />

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {(showAll ? errors : errors.slice(0, 3)).map((error) => {
              const resolvingKey = error.aggregation_key || error.id;
              const occurrenceTotal =
                error.occurrence_total ||
                error.occurrence_count ||
                (error.ids ? error.ids.length : error.count || 1);

              return (
                <Paper
                  key={resolvingKey}
                  elevation={3}
                  sx={{
                    p: 2,
                    borderLeft: 4,
                    borderColor: error.severity === 'critical' ? 'error.main' : 'warning.main',
                    position: 'relative',
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'start',
                      mb: 1.5,
                      gap: 2,
                    }}
                  >
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography variant="h6" fontWeight={600} color="error.main">
                        {error.code || error.error_code}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {error.display_message || error.message_raw || error.message}
                      </Typography>
                    </Box>

                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        flexShrink: 0,
                        flexWrap: 'wrap',
                      }}
                    >
                      <Chip
                        label={error.severity}
                        color={error.severity === 'critical' ? 'error' : 'warning'}
                        size="small"
                        sx={{ textTransform: 'uppercase', fontWeight: 600 }}
                      />
                      {error.count > 1 && (
                        <Chip label={`${error.count} occurrences`} color="info" size="small" />
                      )}
                      <Button
                        variant="outlined"
                        size="small"
                        color="success"
                        startIcon={
                          resolvingErrors[resolvingKey] ? (
                            <CircularProgress size={16} />
                          ) : (
                            <CheckIcon />
                          )
                        }
                        onClick={() => markAsResolved(error)}
                        disabled={resolvingErrors[resolvingKey]}
                        sx={{ minWidth: 130 }}
                      >
                        {resolvingErrors[resolvingKey] ? 'Resolving...' : 'Mark Resolved'}
                      </Button>
                    </Box>
                  </Box>

                  {error.explanation && (
                    <Alert severity="info" sx={{ mb: 1.5 }} icon={<PsychologyIcon />}>
                      <Typography variant="body2" fontWeight={500}>
                        💡 AI Analysis
                      </Typography>
                      <Typography variant="body2">{error.explanation}</Typography>
                    </Alert>
                  )}

                  {error.likely_causes && error.likely_causes.length > 0 && (
                    <Box sx={{ mb: 1.5 }}>
                      <Typography
                        variant="subtitle2"
                        fontWeight={600}
                        color="warning.main"
                        gutterBottom
                      >
                        🔍 Likely Causes:
                      </Typography>
                      <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                        {error.likely_causes.map((cause, idx) => (
                          <Typography
                            key={idx}
                            component="li"
                            variant="body2"
                            color="text.secondary"
                          >
                            {cause}
                          </Typography>
                        ))}
                      </Box>
                    </Box>
                  )}

                  {error.available_fixes && error.available_fixes.length > 0 && (
                    <Box>
                      <Typography
                        variant="subtitle2"
                        fontWeight={600}
                        color="success.main"
                        gutterBottom
                      >
                        ✅ Recommended Fixes:
                      </Typography>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                        {error.available_fixes.map((fix, idx) => (
                          <Paper
                            key={idx}
                            variant="outlined"
                            sx={{
                              p: 1.5,
                              bgcolor: 'success.dark',
                              borderColor: 'success.main',
                            }}
                          >
                            <Typography variant="subtitle2" fontWeight={600}>
                              {fix.title}
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                              {fix.description}
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                              <Chip
                                label={`⏱️ ${fix.estimated_duration_sec}s`}
                                size="small"
                                variant="outlined"
                              />
                              {fix.requires_confirmation && (
                                <Chip
                                  label="⚠️ Requires Confirmation"
                                  size="small"
                                  color="warning"
                                  variant="outlined"
                                />
                              )}
                              {fix.is_destructive && (
                                <Chip
                                  label="🔥 Destructive"
                                  size="small"
                                  color="error"
                                  variant="outlined"
                                />
                              )}
                            </Box>
                          </Paper>
                        ))}
                      </Box>
                    </Box>
                  )}

                  <Box sx={{ mt: 1.5, pt: 1.5, borderTop: 1, borderColor: 'divider' }}>
                    <Typography variant="caption" color="text.secondary">
                      Bot: <strong>{error.bot_id}</strong> • Source: <strong>{error.source}</strong>{' '}
                      • First seen:{' '}
                      <strong>
                        {error.first_seen ? new Date(error.first_seen).toLocaleString() : 'n/a'}
                      </strong>{' '}
                      • Count: <strong>{occurrenceTotal}</strong>
                    </Typography>
                  </Box>
                </Paper>
              );
            })}

            {errors.length > 3 && (
              <Box sx={{ textAlign: 'center', mt: 1 }}>
                <Link
                  component="button"
                  variant="body2"
                  onClick={() => setShowAll(!showAll)}
                  sx={{
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: '0.95rem',
                    textDecoration: 'none',
                    '&:hover': { textDecoration: 'underline' },
                  }}
                >
                  {showAll
                    ? '▲ Show Less'
                    : `▼ Show ${errors.length - 3} More Error${errors.length - 3 > 1 ? 's' : ''}`}
                </Link>
              </Box>
            )}
          </Box>
        </Box>
      )}
    </Paper>
  );
};

const ErrorResolutionPanel = ({
  variant = 'advanced',
  errors = [],
  statistics = SIMPLE_DEFAULT_STATS,
  onErrorUpdate,
  onStatsUpdate,
}) => {
  if (variant === 'simple') {
    return (
      <SimpleErrorResolutionPanel
        errors={errors}
        statistics={statistics}
        onErrorUpdate={onErrorUpdate}
        onStatsUpdate={onStatsUpdate}
      />
    );
  }

  return (
    <AdvancedErrorResolutionPanel
      errors={errors}
      onErrorUpdate={onErrorUpdate}
      onStatsUpdate={onStatsUpdate}
    />
  );
};

export default ErrorResolutionPanel;
