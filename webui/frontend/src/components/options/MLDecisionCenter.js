/**
 * ML Decision Center Component - Phase 4 UI
 *
 * Displays AI decision pipeline with:
 * - Pending decisions for approval
 * - Circuit breaker status
 * - Autonomy level controls
 * - Decision history
 *
 * Created: January 18, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';
import {
  Box,
  Paper,
  Typography,
  Chip,
  Button,
  CircularProgress,
  Tooltip,
  Grid,
  LinearProgress,
  Divider,
  Card,
  CardContent,
  IconButton,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Switch,
  FormControlLabel,
  Slider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import PauseCircleIcon from '@mui/icons-material/PauseCircle';
import PlayCircleIcon from '@mui/icons-material/PlayCircle';
import SecurityIcon from '@mui/icons-material/Security';
import SpeedIcon from '@mui/icons-material/Speed';
import GavelIcon from '@mui/icons-material/Gavel';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import TuneIcon from '@mui/icons-material/Tune';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import ThumbDownIcon from '@mui/icons-material/ThumbDown';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5555';

// Autonomy level descriptions
const AUTONOMY_LEVELS = {
  advisory: {
    label: 'Manual / Advisory',
    description: 'AI provides suggestions only, human executes all trades',
    color: '#9e9e9e',
    sliderValue: 0,
  },
  semi_auto: {
    label: 'Semi-Automatic',
    description: 'AI can execute trades with approval',
    color: '#ff9800',
    sliderValue: 1,
  },
  full_auto: {
    label: 'Full Automatic',
    description: 'AI executes all trades within risk limits',
    color: '#4caf50',
    sliderValue: 2,
  },
};

// Slider value to backend level mapping
const SLIDER_TO_LEVEL = {
  0: 'advisory',
  1: 'semi_auto',
  2: 'full_auto',
};

// Backend level to slider value mapping
const LEVEL_TO_SLIDER = {
  advisory: 0,
  semi_auto: 1,
  full_auto: 2,
};

const MLDecisionCenter = () => {
  const [loading, setLoading] = useState(true);
  const [pendingDecisions, setPendingDecisions] = useState([]);
  const [circuitBreaker, setCircuitBreaker] = useState(null);
  const [engineStatus, setEngineStatus] = useState(null);
  const [error, setError] = useState(null);

  // Dialog states
  const [rejectDialog, setRejectDialog] = useState({ open: false, decisionId: null });
  const [rejectReason, setRejectReason] = useState('');
  const [settingsDialog, setSettingsDialog] = useState(false);

  // Fetch pending decisions
  const fetchPendingDecisions = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/decision/pending`);
      const data = await response.json();
      if (data.success) {
        setPendingDecisions(data.decisions || []);
      }
    } catch (err) {
      console.error('Error fetching decisions:', err);
    }
  }, []);

  // Fetch circuit breaker status
  const fetchCircuitBreaker = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/circuit-breaker/status`);
      const data = await response.json();
      if (data.success) {
        setCircuitBreaker(data.status);
      }
    } catch (err) {
      console.error('Error fetching circuit breaker:', err);
    }
  }, []);

  // Fetch engine status
  const fetchEngineStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/decision/status`);
      const data = await response.json();
      if (data.success) {
        setEngineStatus(data);
      }
    } catch (err) {
      console.error('Error fetching engine status:', err);
    }
  }, []);

  // Approve decision
  const approveDecision = async (decisionId) => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/decision/${decisionId}/approve`, {
        method: 'POST',
      });
      const data = await response.json();
      if (data.success) {
        fetchPendingDecisions();
      } else {
        setError(data.error || 'Failed to approve');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // Reject decision
  const rejectDecision = async () => {
    if (!rejectDialog.decisionId) return;

    try {
      const response = await fetch(
        `${API_BASE}/api/ml/decision/${rejectDialog.decisionId}/reject`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: rejectReason || 'Manual rejection' }),
        }
      );
      const data = await response.json();
      if (data.success) {
        fetchPendingDecisions();
        setRejectDialog({ open: false, decisionId: null });
        setRejectReason('');
      } else {
        setError(data.error || 'Failed to reject');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // Set autonomy level
  const setAutonomyLevel = async (sliderValue) => {
    try {
      // Map slider value to backend enum
      const level = SLIDER_TO_LEVEL[sliderValue] || 'advisory';

      const response = await fetch(`${API_BASE}/api/ml/decision/autonomy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level }),
      });
      const data = await response.json();
      if (data.success) {
        fetchEngineStatus();
      } else {
        setError(data.error || 'Failed to set autonomy level');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // Reset circuit breaker
  const resetCircuitBreaker = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/circuit-breaker/reset`, {
        method: 'POST',
      });
      const data = await response.json();
      if (data.success) {
        fetchCircuitBreaker();
      } else {
        setError(data.error || 'Failed to reset circuit breaker');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // Initial load
  useEffect(() => {
    Promise.all([fetchPendingDecisions(), fetchCircuitBreaker(), fetchEngineStatus()]).finally(() =>
      setLoading(false)
    );
  }, [fetchPendingDecisions, fetchCircuitBreaker, fetchEngineStatus]);

  // Auto-refresh decisions & circuit breaker — pauses when tab is hidden
  const refreshMLData = useCallback(() => {
    fetchPendingDecisions();
    fetchCircuitBreaker();
  }, [fetchPendingDecisions, fetchCircuitBreaker]);
  useVisibilityAwarePolling(refreshMLData, 30000, 120000);

  // Render circuit breaker card
  const renderCircuitBreaker = () => {
    if (!circuitBreaker) return null;

    const isTripped = circuitBreaker.is_tripped;

    return (
      <Card
        sx={{
          mb: 2,
          bgcolor: isTripped ? 'rgba(244, 67, 54, 0.1)' : 'rgba(76, 175, 80, 0.1)',
          border: `2px solid ${isTripped ? '#f44336' : '#4caf50'}`,
        }}
      >
        <CardContent>
          <Box
            sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <SecurityIcon sx={{ color: isTripped ? '#f44336' : '#4caf50' }} />
              <Typography variant="h6">Circuit Breaker</Typography>
              <Chip
                label={isTripped ? 'TRIPPED' : 'ACTIVE'}
                color={isTripped ? 'error' : 'success'}
                size="small"
              />
            </Box>

            {isTripped && (
              <Button
                variant="outlined"
                color="warning"
                startIcon={<RestartAltIcon />}
                onClick={resetCircuitBreaker}
                size="small"
              >
                Reset
              </Button>
            )}
          </Box>

          {isTripped && circuitBreaker.trip_reason && (
            <Alert severity="error" sx={{ mb: 2 }}>
              <Typography variant="subtitle2">Trip Reason:</Typography>
              {circuitBreaker.trip_reason}
            </Alert>
          )}

          <Grid container spacing={3}>
            <Grid item xs={3}>
              <Typography variant="caption" color="text.secondary">
                Trades Today
              </Typography>
              <Typography variant="h6">{circuitBreaker.trades_today || 0}</Typography>
              <Typography variant="caption" color="text.secondary">
                Limit: {circuitBreaker.daily_trade_limit || 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={3}>
              <Typography variant="caption" color="text.secondary">
                Daily PnL
              </Typography>
              <Typography
                variant="h6"
                color={circuitBreaker.daily_pnl >= 0 ? 'success.main' : 'error.main'}
              >
                ${circuitBreaker.daily_pnl?.toFixed(2) || '0.00'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Limit: ${circuitBreaker.daily_loss_limit || 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={3}>
              <Typography variant="caption" color="text.secondary">
                Consecutive Losses
              </Typography>
              <Typography
                variant="h6"
                color={circuitBreaker.consecutive_losses >= 3 ? 'error.main' : 'inherit'}
              >
                {circuitBreaker.consecutive_losses || 0}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Max: {circuitBreaker.max_consecutive_losses || 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={3}>
              <Typography variant="caption" color="text.secondary">
                Win Rate
              </Typography>
              <Typography variant="h6">
                {(circuitBreaker.recent_win_rate * 100)?.toFixed(0) || 0}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Min: {(circuitBreaker.min_win_rate * 100)?.toFixed(0) || 0}%
              </Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    );
  };

  // Render autonomy level control
  const renderAutonomyControl = () => {
    const backendLevel = engineStatus?.autonomy_level || 'advisory';
    const sliderValue = LEVEL_TO_SLIDER[backendLevel] ?? 0;
    const levelInfo = AUTONOMY_LEVELS[backendLevel] || AUTONOMY_LEVELS.advisory;

    return (
      <Card sx={{ mb: 2, bgcolor: 'rgba(30, 35, 50, 0.9)' }}>
        <CardContent>
          <Box
            sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <SpeedIcon />
              <Typography variant="h6">Autonomy Level</Typography>
            </Box>
            <IconButton onClick={() => setSettingsDialog(true)}>
              <TuneIcon />
            </IconButton>
          </Box>

          <Box sx={{ px: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="subtitle1" sx={{ color: levelInfo?.color }}>
                {levelInfo?.label}
              </Typography>
              <Chip label={levelInfo?.label} size="small" />
            </Box>

            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {levelInfo?.description}
            </Typography>

            <Slider
              value={sliderValue}
              onChange={(e, value) => setAutonomyLevel(value)}
              min={0}
              max={2}
              step={1}
              marks={[
                { value: 0, label: 'Manual' },
                { value: 1, label: 'Semi-Auto' },
                { value: 2, label: 'Full Auto' },
              ]}
              sx={{
                '& .MuiSlider-thumb': {
                  backgroundColor: levelInfo?.color,
                },
                '& .MuiSlider-track': {
                  backgroundColor: levelInfo?.color,
                },
              }}
            />

            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Manual
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Full Auto
              </Typography>
            </Box>
          </Box>
        </CardContent>
      </Card>
    );
  };

  // Render pending decisions
  const renderPendingDecisions = () => {
    return (
      <Card sx={{ bgcolor: 'rgba(30, 35, 50, 0.9)' }}>
        <CardContent>
          <Box
            sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <GavelIcon />
              <Typography variant="h6">Pending Decisions</Typography>
              {pendingDecisions.length > 0 && (
                <Chip label={pendingDecisions.length} color="warning" size="small" />
              )}
            </Box>
          </Box>

          {pendingDecisions.length === 0 ? (
            <Alert severity="info" sx={{ bgcolor: 'rgba(33, 150, 243, 0.1)' }}>
              No pending decisions. AI is either operating autonomously or waiting for
              opportunities.
            </Alert>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Signal</TableCell>
                    <TableCell>Details</TableCell>
                    <TableCell>Confidence</TableCell>
                    <TableCell>Risk</TableCell>
                    <TableCell>Reason</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {pendingDecisions.map((decision, i) => (
                    <TableRow key={decision.decision_id || i}>
                      <TableCell>
                        <Chip
                          label={`${decision.action} ${decision.option_type?.toUpperCase()}`}
                          color={decision.option_type === 'call' ? 'success' : 'error'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          ${decision.strike?.toLocaleString()} @ ${decision.price?.toFixed(2)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <LinearProgress
                            variant="determinate"
                            value={(decision.confidence || 0) * 100}
                            sx={{ width: 50, height: 6, borderRadius: 3 }}
                          />
                          <Typography variant="caption">
                            {((decision.confidence || 0) * 100).toFixed(0)}%
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={decision.risk_level || 'UNKNOWN'}
                          color={
                            decision.risk_level === 'LOW'
                              ? 'success'
                              : decision.risk_level === 'MEDIUM'
                                ? 'warning'
                                : 'error'
                          }
                          size="small"
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Tooltip title={decision.requires_approval_reason || 'Pending review'}>
                          <Typography
                            variant="caption"
                            noWrap
                            sx={{ maxWidth: 150, display: 'block' }}
                          >
                            {decision.requires_approval_reason || 'Manual review'}
                          </Typography>
                        </Tooltip>
                      </TableCell>
                      <TableCell align="right">
                        <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                          <Tooltip title="Approve">
                            <IconButton
                              color="success"
                              size="small"
                              onClick={() => approveDecision(decision.decision_id)}
                            >
                              <ThumbUpIcon />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Reject">
                            <IconButton
                              color="error"
                              size="small"
                              onClick={() =>
                                setRejectDialog({ open: true, decisionId: decision.decision_id })
                              }
                            >
                              <ThumbDownIcon />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    );
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Paper sx={{ p: 2, bgcolor: 'rgba(18, 22, 35, 0.95)' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <GavelIcon />
          Decision Center
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {engineStatus?.is_enabled ? (
            <Chip
              icon={<PlayCircleIcon />}
              label="Engine Active"
              color="success"
              variant="outlined"
            />
          ) : (
            <Chip
              icon={<PauseCircleIcon />}
              label="Engine Paused"
              color="warning"
              variant="outlined"
            />
          )}
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Circuit Breaker */}
      {renderCircuitBreaker()}

      {/* Autonomy Control */}
      {renderAutonomyControl()}

      {/* Pending Decisions */}
      {renderPendingDecisions()}

      {/* Reject Dialog */}
      <Dialog
        open={rejectDialog.open}
        onClose={() => setRejectDialog({ open: false, decisionId: null })}
      >
        <DialogTitle>Reject Decision</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Rejection Reason"
            fullWidth
            multiline
            rows={3}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="Optional: Explain why this trade shouldn't be taken..."
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejectDialog({ open: false, decisionId: null })}>Cancel</Button>
          <Button onClick={rejectDecision} color="error" variant="contained">
            Reject
          </Button>
        </DialogActions>
      </Dialog>

      {/* Settings Dialog */}
      <Dialog
        open={settingsDialog}
        onClose={() => setSettingsDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Decision Engine Settings</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Risk Limits
            </Typography>

            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  label="Max Position Size ($)"
                  type="number"
                  fullWidth
                  size="small"
                  defaultValue={engineStatus?.risk_limits?.max_position_size || 1000}
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  label="Daily Loss Limit ($)"
                  type="number"
                  fullWidth
                  size="small"
                  defaultValue={engineStatus?.risk_limits?.daily_loss_limit || 500}
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  label="Max Daily Trades"
                  type="number"
                  fullWidth
                  size="small"
                  defaultValue={engineStatus?.risk_limits?.max_daily_trades || 10}
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  label="Max Consecutive Losses"
                  type="number"
                  fullWidth
                  size="small"
                  defaultValue={engineStatus?.risk_limits?.max_consecutive_losses || 3}
                />
              </Grid>
            </Grid>

            <Divider sx={{ my: 3 }} />

            <Typography variant="subtitle2" gutterBottom>
              Features
            </Typography>

            <FormControlLabel
              control={<Switch defaultChecked />}
              label="Enable style matching requirement"
            />
            <FormControlLabel control={<Switch defaultChecked />} label="Require regime analysis" />
            <FormControlLabel control={<Switch />} label="Allow after-hours trading" />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSettingsDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => setSettingsDialog(false)}>
            Save Settings
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
};

export default MLDecisionCenter;
