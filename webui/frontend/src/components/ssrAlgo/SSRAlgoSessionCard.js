/**
 * SSR Algo Session Card
 * 
 * Displays a single SSR Algo session with controls and status.
 * Shows positions, monitor status, and control buttons.
 * 
 * Created: February 2, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Card,
  CardContent,
  CardActions,
  Typography,
  Chip,
  IconButton,
  Button,
  Collapse,
  Grid,
  LinearProgress,
  Tooltip,
  Divider,
  Alert,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Warning as WarningIcon,
  Timer as TimerIcon,
} from '@mui/icons-material';
import ssrAlgoService from './ssrAlgoService';

// Status badge colors
const STATUS_COLORS = {
  IDLE: 'default',
  SELECTING_STRIKES: 'info',
  EXECUTING_AUTO_LOOP: 'warning',
  MONITORING: 'success',
  PAUSED: 'warning',
  ERROR: 'error',
  STOPPED: 'default',
};

// Status labels with descriptions
const STATUS_LABELS = {
  IDLE: 'Ready to Start',
  SELECTING_STRIKES: 'Selecting Strikes...',
  EXECUTING_AUTO_LOOP: 'Executing Rounds...',
  MONITORING: 'Active - Monitoring',
  PAUSED: 'Paused',
  ERROR: 'Error - Needs Attention',
  STOPPED: 'Completed/Stopped',
};

/**
 * Session card component
 */
const SSRAlgoSessionCard = ({ session, onRefresh, onDelete }) => {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [monitorStatus, setMonitorStatus] = useState(null);
  const [payoffData, setPayoffData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [orderStatus, setOrderStatus] = useState({ pending: 0, filled: 0 });

  const sessionId = session?.session_id;
  const status = session?.status || 'IDLE';
  const isActive = ['MONITORING', 'EXECUTING_AUTO_LOOP', 'SELECTING_STRIKES'].includes(status);
  const isPaused = status === 'PAUSED';
  const isStopped = status === 'STOPPED';
  const isError = status === 'ERROR';
  const isIdle = status === 'IDLE';

  // Fetch logs - defined first for use by other callbacks
  const fetchLogs = useCallback(async () => {
    if (!sessionId) return;
    
    try {
      const result = await ssrAlgoService.getSessionLogs(sessionId, 20);
      if (result.success) {
        setLogs(result.logs || []);
      }
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    }
  }, [sessionId]);

  // Sync orders with exchange (check fill status)
  const syncOrders = useCallback(async () => {
    if (!sessionId || isIdle || isStopped) return;
    
    try {
      const result = await ssrAlgoService.syncOrders(sessionId);
      if (result.success) {
        setOrderStatus({
          pending: result.pending || 0,
          filled: result.filled_orders?.length || 0,
          roundsPlaced: result.rounds_placed || 0,
          roundsCompleted: result.rounds_completed || 0
        });
        // If orders were just filled, refresh logs to show the fills
        if (result.filled > 0) {
          fetchLogs();
          if (onRefresh) onRefresh();
        }
      }
    } catch (err) {
      console.error('Failed to sync orders:', err);
    }
  }, [sessionId, isIdle, isStopped, fetchLogs, onRefresh]);

  // Fetch monitor status
  const fetchMonitorStatus = useCallback(async () => {
    if (!sessionId || isIdle || isStopped) return;
    
    try {
      const result = await ssrAlgoService.getMonitorStatus(sessionId);
      if (result.success) {
        setMonitorStatus(result.monitor);
        // Also get max loss points from this response
        if (result.max_loss_points) {
          setPayoffData(prev => ({ ...prev, max_loss_points: result.max_loss_points }));
        }
      }
    } catch (err) {
      console.error('Failed to fetch monitor status:', err);
    }
  }, [sessionId, isIdle, isStopped]);

  // Fetch payoff data
  const fetchPayoffData = useCallback(async () => {
    if (!sessionId) return;
    
    try {
      const result = await ssrAlgoService.getSessionPayoff(sessionId);
      if (result.success) {
        setPayoffData(result);
      }
    } catch (err) {
      console.error('Failed to fetch payoff data:', err);
    }
  }, [sessionId]);

  // Fetch data for all sessions (including stopped)
  useEffect(() => {
    // Always fetch payoff and logs on mount
    fetchPayoffData();
    fetchLogs();

    // For active/paused sessions, also start auto-refresh
    if (!isActive && !isPaused) return;

    fetchMonitorStatus();
    syncOrders(); // Initial sync

    const interval = setInterval(() => {
      fetchMonitorStatus();
      fetchLogs();
      syncOrders(); // Check for order fills
    }, 5000); // Every 5 seconds

    return () => clearInterval(interval);
  }, [isActive, isPaused, fetchMonitorStatus, fetchPayoffData, fetchLogs]);

  // Session control actions
  const handleStart = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await ssrAlgoService.startSession(sessionId);
      if (!result.success) {
        setError(result.error);
      } else {
        onRefresh?.();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePause = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await ssrAlgoService.pauseSession(sessionId);
      if (!result.success) {
        setError(result.error);
      } else {
        onRefresh?.();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await ssrAlgoService.retrySession(sessionId);
      if (!result.success) {
        setError(result.error);
      } else {
        onRefresh?.();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResume = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await ssrAlgoService.resumeSession(sessionId);
      if (!result.success) {
        setError(result.error);
      } else {
        onRefresh?.();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    if (!window.confirm('Are you sure you want to stop this session?')) return;
    
    setLoading(true);
    setError(null);
    try {
      const result = await ssrAlgoService.stopSession(sessionId);
      if (!result.success) {
        setError(result.error);
      } else {
        onRefresh?.();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this session?')) return;
    
    setLoading(true);
    setError(null);
    try {
      const result = await ssrAlgoService.deleteSession(sessionId);
      if (!result.success) {
        setError(result.error);
      } else {
        onDelete?.(sessionId);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Format time active
  const formatTimeActive = () => {
    if (!session?.started_at) return '-';
    const start = new Date(session.started_at);
    const now = new Date();
    const diff = Math.floor((now - start) / 1000 / 60); // minutes
    if (diff < 60) return `${diff}m`;
    const hours = Math.floor(diff / 60);
    const mins = diff % 60;
    return `${hours}h ${mins}m`;
  };

  // Get dwell status display
  const getDwellDisplay = () => {
    if (!monitorStatus?.dwell_status) return null;
    const dwell = monitorStatus.dwell_status;
    
    if (!dwell.current_zone) return null;
    
    const progress = (dwell.time_in_zone_minutes / dwell.dwell_threshold_minutes) * 100;
    
    return (
      <Box sx={{ mt: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
          <WarningIcon color="warning" fontSize="small" />
          <Typography variant="body2" color="warning.main">
            In {dwell.current_zone.toUpperCase()} max loss zone: {dwell.time_in_zone_minutes.toFixed(1)}/{dwell.dwell_threshold_minutes}min
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={Math.min(100, progress)}
          color={progress > 80 ? 'error' : 'warning'}
          sx={{ height: 6, borderRadius: 3 }}
        />
      </Box>
    );
  };

  return (
    <Card 
      sx={{ 
        mb: 1,
        background: isActive 
          ? 'linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(30, 41, 59, 0.95) 100%)'
          : isIdle
          ? 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(30, 41, 59, 0.95) 100%)'
          : 'linear-gradient(135deg, rgba(51, 65, 85, 0.9) 0%, rgba(30, 41, 59, 0.95) 100%)',
        border: isActive ? '2px solid' : '1px solid',
        borderColor: isActive 
          ? 'rgba(34, 197, 94, 0.6)' 
          : isIdle 
          ? 'rgba(59, 130, 246, 0.4)'
          : 'rgba(100, 116, 139, 0.4)',
        borderRadius: 2,
        boxShadow: isActive 
          ? '0 4px 20px rgba(34, 197, 94, 0.2)'
          : '0 2px 10px rgba(0, 0, 0, 0.3)',
        transition: 'all 0.3s ease',
        '&:hover': {
          borderColor: isActive ? 'rgba(34, 197, 94, 0.8)' : 'rgba(56, 189, 248, 0.5)',
          boxShadow: '0 6px 24px rgba(0, 0, 0, 0.4)',
          transform: 'translateY(-2px)'
        }
      }}
    >
      {loading && <LinearProgress />}
      
      <CardContent sx={{ pb: 1, pt: 2 }}>
        {/* Idle Session Info Banner */}
        {isIdle && !session?.error && (
          <Alert 
            severity="info" 
            sx={{ 
              mb: 2,
              bgcolor: 'rgba(59, 130, 246, 0.15)',
              border: '2px solid rgba(59, 130, 246, 0.5)',
              '& .MuiAlert-icon': { color: '#60a5fa' },
              '& .MuiAlert-message': { color: '#e0f2fe' }
            }}
          >
            <strong>Session ready.</strong> Click "Start" to select strikes and execute the butterfly strategy with {session?.auto_loop_rounds || 2} auto-loop rounds.
          </Alert>
        )}
        
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
          <Box>
            <Typography 
              variant="h6" 
              component="div" 
              sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 1.5,
                fontWeight: 600,
                color: '#f1f5f9'
              }}
            >
              <Box sx={{ 
                fontSize: '1.5rem',
                filter: 'drop-shadow(0 0 8px rgba(255, 255, 255, 0.3))'
              }}>
                {session?.underlying === 'ETH' ? '⟠' : '₿'}
              </Box>
              {session?.underlying || 'BTC'}
              <Chip 
                size="small" 
                label={STATUS_LABELS[status] || status}
                color={STATUS_COLORS[status] || 'default'}
                sx={{ fontWeight: 600 }}
              />
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, fontFamily: 'monospace', fontSize: '0.75rem' }}>
              {sessionId}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Tooltip title="Refresh">
              <IconButton size="small" onClick={onRefresh} disabled={loading}>
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            {(isIdle || isStopped) && (
              <Tooltip title="Delete">
                <IconButton size="small" onClick={handleDelete} disabled={loading} color="error">
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        </Box>

        {/* Session Info */}
        <Grid container spacing={2} sx={{ mb: 1 }}>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">Expiry</Typography>
            <Typography variant="body2">{session?.expiry}</Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">Rounds Completed</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600, color: orderStatus.pending > 0 ? 'warning.main' : 'success.main' }}>
              {orderStatus.roundsCompleted || session?.rounds_completed || 0} / {session?.auto_loop_rounds || 2}
              {orderStatus.pending > 0 && (
                <Typography component="span" variant="caption" sx={{ ml: 0.5, color: 'warning.main' }}>
                  ({orderStatus.pending} pending)
                </Typography>
              )}
            </Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">Open Positions</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {(session?.rounds_completed || 0) * 6} legs
            </Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">Current Price</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600, color: '#38bdf8' }}>
              ${monitorStatus?.last_price?.toLocaleString() || payoffData?.spot_price?.toLocaleString() || '-'}
            </Typography>
          </Grid>
        </Grid>

        {/* Adjustment Trigger Zones - THE KEY INFO */}
        {isActive && payoffData?.adjustment_triggers && (
          <Box sx={{ 
            p: 1.5, 
            mb: 1, 
            bgcolor: 'rgba(251, 191, 36, 0.15)', 
            borderRadius: 1,
            border: '2px solid rgba(251, 191, 36, 0.5)',
            boxShadow: '0 0 12px rgba(251, 191, 36, 0.2)'
          }}>
            <Typography variant="caption" sx={{ display: 'block', mb: 0.5, color: '#fcd34d', fontWeight: 600 }}>
              ⚠️ Adjustment will trigger when price reaches:
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              {payoffData.adjustment_triggers.lower_trigger && (
                <Typography variant="body2" sx={{ color: '#fca5a5', fontWeight: 700, fontSize: '0.95rem' }}>
                  📉 Lower: ${payoffData.adjustment_triggers.lower_trigger.toLocaleString()}
                  <Typography component="span" variant="caption" sx={{ ml: 0.5, color: '#cbd5e1' }}>
                    (±{payoffData.adjustment_triggers.tolerance})
                  </Typography>
                </Typography>
              )}
              {payoffData.adjustment_triggers.upper_trigger && (
                <Typography variant="body2" sx={{ color: '#fca5a5', fontWeight: 700, fontSize: '0.95rem' }}>
                  📈 Upper: ${payoffData.adjustment_triggers.upper_trigger.toLocaleString()}
                  <Typography component="span" variant="caption" sx={{ ml: 0.5, color: '#cbd5e1' }}>
                    (±{payoffData.adjustment_triggers.tolerance})
                  </Typography>
                </Typography>
              )}
            </Box>
            {payoffData.atm_strike && (
              <Typography variant="caption" sx={{ mt: 0.5, display: 'block', color: '#cbd5e1' }}>
                ATM Strike: {payoffData.atm_strike.toLocaleString()} | 
                Dwell Time: {session?.dwell_time_minutes || 10} min
              </Typography>
            )}
          </Box>
        )}

        {/* Active Session Details - Show positions summary */}
        {isActive && session?.positions?.length > 0 && (
          <Alert 
            severity="success" 
            sx={{ 
              mb: 1, 
              py: 0.5,
              bgcolor: 'rgba(34, 197, 94, 0.15)',
              border: '2px solid rgba(34, 197, 94, 0.5)',
              '& .MuiAlert-icon': { color: '#4ade80' },
              '& .MuiAlert-message': { color: '#d1fae5', fontWeight: 500 }
            }}
          >  <strong>Positions Active:</strong> {session.rounds_completed || 1} round(s) × 6 legs = <strong>{(session.rounds_completed || 1) * 6} positions</strong>
            {' | '}
            ATM Strike: <strong>{session.positions[session.positions.length - 1]?.atm_strike?.toLocaleString()}</strong>
          </Alert>
        )}

        {/* Max Loss Zones */}
        {payoffData?.max_loss_points && (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
            {payoffData.max_loss_points.max_loss_lower && (
              <Chip
                size="small"
                icon={<TrendingDownIcon />}
                label={`Lower: ${payoffData.max_loss_points.max_loss_lower.toLocaleString()}`}
                color="error"
                variant="outlined"
              />
            )}
            {payoffData.max_loss_points.max_loss_upper && (
              <Chip
                size="small"
                icon={<TrendingUpIcon />}
                label={`Upper: ${payoffData.max_loss_points.max_loss_upper.toLocaleString()}`}
                color="error"
                variant="outlined"
              />
            )}
          </Box>
        )}

        {/* Dwell Progress */}
        {getDwellDisplay()}

        {/* Session Error (from backend) */}
        {(session?.error || isError) && (
          <Alert severity="error" sx={{ mt: 1 }}>
            <strong>Session Error:</strong> {session.error || 'Unknown error occurred'}
            <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
              💡 Click "Retry" to reset and try again, or "Stop" to end the session.
            </Typography>
          </Alert>
        )}

        {/* Error (from local actions) */}
        {error && (
          <Alert severity="error" sx={{ mt: 1 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
      </CardContent>

      {/* Control Buttons */}
      <CardActions sx={{ justifyContent: 'space-between', px: 2 }}>
        <Box>
          {isIdle && (
            <Button
              size="small"
              variant="contained"
              color="primary"
              startIcon={<PlayIcon />}
              onClick={handleStart}
              disabled={loading}
            >
              Start
            </Button>
          )}
          {isError && (
            <>
              <Button
                size="small"
                variant="contained"
                color="warning"
                startIcon={<RefreshIcon />}
                onClick={handleRetry}
                disabled={loading}
              >
                Retry
              </Button>
              <Button
                size="small"
                variant="outlined"
                color="error"
                startIcon={<StopIcon />}
                onClick={handleStop}
                disabled={loading}
                sx={{ ml: 1 }}
              >
                Stop
              </Button>
            </>
          )}
          {isActive && (
            <Button
              size="small"
              variant="outlined"
              color="warning"
              startIcon={<PauseIcon />}
              onClick={handlePause}
              disabled={loading}
            >
              Pause
            </Button>
          )}
          {isPaused && (
            <Button
              size="small"
              variant="contained"
              color="success"
              startIcon={<PlayIcon />}
              onClick={handleResume}
              disabled={loading}
            >
              Resume
            </Button>
          )}
          {(isActive || isPaused) && (
            <Button
              size="small"
              variant="outlined"
              color="error"
              startIcon={<StopIcon />}
              onClick={handleStop}
              disabled={loading}
              sx={{ ml: 1 }}
            >
              Stop
            </Button>
          )}
        </Box>
        <IconButton
          size="small"
          onClick={() => setExpanded(!expanded)}
          sx={{ transform: expanded ? 'rotate(180deg)' : 'none', transition: '0.3s' }}
        >
          <ExpandMoreIcon />
        </IconButton>
      </CardActions>

      {/* Expanded Details */}
      <Collapse in={expanded}>
        <Divider />
        <CardContent>
          {/* Activity Log Panel */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              📋 Activity Log
            </Typography>
            <Box sx={{ 
              maxHeight: 150, 
              overflow: 'auto', 
              bgcolor: 'rgba(0, 0, 0, 0.2)', 
              p: 1, 
              borderRadius: 1,
              fontFamily: 'monospace',
              fontSize: '0.75rem'
            }}>
              {logs.length > 0 ? (
                logs.slice().reverse().map((logEntry, idx) => (
                  <Box key={idx} sx={{ 
                    py: 0.3, 
                    borderBottom: idx < logs.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
                    display: 'flex',
                    gap: 1
                  }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', minWidth: 70 }}>
                      {new Date(logEntry.timestamp).toLocaleTimeString()}
                    </Typography>
                    <Typography 
                      variant="caption" 
                      sx={{ 
                        color: logEntry.level === 'error' ? '#f87171' : 
                               logEntry.level === 'warn' ? '#fbbf24' : 
                               logEntry.level === 'success' ? '#4ade80' : '#94a3b8'
                      }}
                    >
                      {logEntry.message}
                    </Typography>
                  </Box>
                ))
              ) : (
                <Typography variant="caption" color="text.secondary">
                  No activity logs yet. Logs will appear when session starts.
                </Typography>
              )}
            </Box>
          </Box>

          <Typography variant="subtitle2" gutterBottom>Positions</Typography>
          {session?.positions?.length > 0 ? (
            <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
              {session.positions.map((posGroup, idx) => (
                <Box key={idx} sx={{ mb: 1, p: 1, bgcolor: 'background.default', borderRadius: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    Round #{idx + 1} - ATM Strike: {posGroup.atm_strike?.toLocaleString()}
                  </Typography>
                  <Grid container spacing={1} sx={{ mt: 0.5 }}>
                    <Grid item xs={6}>
                      <Chip size="small" label={`ATM CE Sell: ${posGroup.atm_ce?.symbol?.split('-')[2]}`} color="error" variant="outlined" />
                    </Grid>
                    <Grid item xs={6}>
                      <Chip size="small" label={`ATM PE Sell: ${posGroup.atm_pe?.symbol?.split('-')[2]}`} color="error" variant="outlined" />
                    </Grid>
                    <Grid item xs={6}>
                      <Chip size="small" label={`OTM CE Buy x2: ${posGroup.otm_ce_buy?.symbol?.split('-')[2]}`} color="success" variant="outlined" />
                    </Grid>
                    <Grid item xs={6}>
                      <Chip size="small" label={`OTM PE Buy x2: ${posGroup.otm_pe_buy?.symbol?.split('-')[2]}`} color="success" variant="outlined" />
                    </Grid>
                    <Grid item xs={6}>
                      <Chip size="small" label={`Far CE Sell: ${posGroup.far_otm_ce?.symbol?.split('-')[2]}`} color="warning" variant="outlined" />
                    </Grid>
                    <Grid item xs={6}>
                      <Chip size="small" label={`Far PE Sell: ${posGroup.far_otm_pe?.symbol?.split('-')[2]}`} color="warning" variant="outlined" />
                    </Grid>
                  </Grid>
                </Box>
              ))}
            </Box>
          ) : (
            <Typography variant="body2" color="text.secondary">No positions yet</Typography>
          )}

          {/* Payoff Summary */}
          {payoffData && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>Payoff Summary</Typography>
              <Grid container spacing={1}>
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">Net Premium</Typography>
                  <Typography variant="body2" color={payoffData.net_premium >= 0 ? 'success.main' : 'error.main'}>
                    ${payoffData.net_premium?.toFixed(2)}
                  </Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">Max Profit</Typography>
                  <Typography variant="body2" color="success.main">
                    ${payoffData.max_loss_points?.max_profit_value?.toFixed(2) || '-'}
                  </Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">Max Loss</Typography>
                  <Typography variant="body2" color="error.main">
                    ${payoffData.max_loss_points?.max_loss_value?.toFixed(2) || '-'}
                  </Typography>
                </Grid>
              </Grid>
              {payoffData.breakevens?.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  <Typography variant="caption" color="text.secondary">Breakevens: </Typography>
                  <Typography variant="body2" component="span">
                    {payoffData.breakevens.map(b => b.toLocaleString()).join(', ')}
                  </Typography>
                </Box>
              )}
            </Box>
          )}
        </CardContent>
      </Collapse>
    </Card>
  );
};

// PropTypes for better developer experience
SSRAlgoSessionCard.propTypes = {
  /** Session object containing id, status, positions, etc. */
  session: PropTypes.shape({
    session_id: PropTypes.string.isRequired,
    status: PropTypes.string,
    underlying: PropTypes.string,
    expiry: PropTypes.string,
    positions: PropTypes.array,
    trigger_count: PropTypes.number,
    auto_loop_rounds: PropTypes.number,
    created_at: PropTypes.string,
  }).isRequired,
  /** Callback when session data should be refreshed */
  onRefresh: PropTypes.func,
  /** Callback when session is deleted */
  onDelete: PropTypes.func,
};

SSRAlgoSessionCard.defaultProps = {
  onRefresh: () => {},
  onDelete: () => {},
};

export default SSRAlgoSessionCard;
