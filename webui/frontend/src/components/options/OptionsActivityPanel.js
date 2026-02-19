/**
 * Options Activity Panel
 * ======================
 * Real-time monitoring of background options trading activities
 * Shows max loss monitoring, warnings, position checks, and auto-close actions
 * 
 * Created: January 31, 2026
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Tooltip,
  Chip,
  LinearProgress,
  Divider,
  Alert,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ErrorIcon from '@mui/icons-material/Error';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PlayCircleIcon from '@mui/icons-material/PlayCircle';

export default function OptionsActivityPanel({ refreshTrigger = 0 }) {
  const [activityData, setActivityData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const intervalRef = useRef(null);

  // Fetch monitoring activity
  const fetchActivity = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/options/monitoring-activity?limit=100');
      
      if (response.ok) {
        const data = await response.json();
        setActivityData(data);
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Failed to fetch activity');
      }
    } catch (err) {
      setError(err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh every 10 seconds for monitoring
  useEffect(() => {
    fetchActivity();
    intervalRef.current = setInterval(fetchActivity, 10000);
    
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  // Manual refresh when trigger changes
  useEffect(() => {
    if (refreshTrigger > 0) {
      fetchActivity();
    }
  }, [refreshTrigger]);

  const getEventIcon = (type) => {
    switch (type) {
      case 'breach':
      case 'closing':
        return <ErrorIcon sx={{ color: '#ef4444', fontSize: '1rem' }} />;
      case 'warning':
        return <WarningAmberIcon sx={{ color: '#f59e0b', fontSize: '1rem' }} />;
      case 'check_start':
      case 'position_check':
        return <MonitorHeartIcon sx={{ color: '#3b82f6', fontSize: '1rem' }} />;
      case 'monitor_start':
        return <PlayCircleIcon sx={{ color: '#22c55e', fontSize: '1rem' }} />;
      case 'idle':
        return <CheckCircleIcon sx={{ color: '#6b7280', fontSize: '1rem' }} />;
      default:
        return <MonitorHeartIcon sx={{ color: '#94a3b8', fontSize: '1rem' }} />;
    }
  };

  const getEventColor = (type) => {
    switch (type) {
      case 'breach':
      case 'closing':
        return '#ef4444';
      case 'warning':
        return '#f59e0b';
      case 'check_start':
      case 'position_check':
        return '#3b82f6';
      case 'monitor_start':
        return '#22c55e';
      case 'idle':
        return '#6b7280';
      default:
        return '#94a3b8';
    }
  };

  const getEventBgColor = (type) => {
    switch (type) {
      case 'breach':
      case 'closing':
        return 'rgba(239, 68, 68, 0.15)';
      case 'warning':
        return 'rgba(245, 158, 11, 0.15)';
      case 'check_start':
      case 'position_check':
        return 'rgba(59, 130, 246, 0.1)';
      default:
        return 'transparent';
    }
  };

  if (!expanded) {
    return (
      <Paper sx={{ p: 1.5, bgcolor: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(71, 85, 105, 0.3)' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="subtitle2" sx={{ color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 1 }}>
            <MonitorHeartIcon sx={{ fontSize: '1rem' }} /> Monitoring Activity
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            {activityData && (
              <>
                <Chip 
                  label={activityData.monitorStatus?.running ? '🟢 Running' : '🔴 Stopped'}
                  size="small"
                  sx={{ 
                    bgcolor: activityData.monitorStatus?.running ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                    color: activityData.monitorStatus?.running ? '#22c55e' : '#ef4444',
                    fontSize: '0.7rem'
                  }}
                />
                <Chip 
                  label={`${activityData.activeLimits?.total || 0} Limits`}
                  size="small"
                  sx={{ bgcolor: 'rgba(59, 130, 246, 0.2)', color: '#3b82f6', fontSize: '0.7rem' }}
                />
              </>
            )}
            <IconButton size="small" onClick={() => setExpanded(true)} sx={{ color: '#94a3b8' }}>
              <ExpandMoreIcon />
            </IconButton>
          </Box>
        </Box>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 2, bgcolor: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(71, 85, 105, 0.3)' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6" sx={{ color: '#e2e8f0', fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
          <MonitorHeartIcon /> Monitoring Activity
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Refresh">
            <IconButton size="small" onClick={fetchActivity} disabled={loading} sx={{ color: '#94a3b8' }}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <IconButton size="small" onClick={() => setExpanded(false)} sx={{ color: '#94a3b8' }}>
            <ExpandLessIcon />
          </IconButton>
        </Box>
      </Box>

      {loading && <LinearProgress sx={{ mb: 2 }} />}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {activityData && (
        <>
          {/* Monitor Status Bar */}
          <Box sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            p: 1.5,
            mb: 2,
            borderRadius: 1,
            bgcolor: 'rgba(30, 41, 59, 0.6)',
            border: '1px solid rgba(148, 163, 184, 0.2)'
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Chip 
                icon={activityData.monitorStatus?.running ? 
                  <PlayCircleIcon sx={{ color: '#22c55e !important' }} /> : 
                  <ErrorIcon sx={{ color: '#ef4444 !important' }} />
                }
                label={activityData.monitorStatus?.running ? 'Monitor Running' : 'Monitor Stopped'}
                size="small"
                sx={{ 
                  bgcolor: activityData.monitorStatus?.running ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                  color: activityData.monitorStatus?.running ? '#22c55e' : '#ef4444',
                  fontWeight: 600
                }}
              />
              <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                Checks: {activityData.monitorStatus?.check_count || 0}
              </Typography>
              <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                Interval: {activityData.monitorStatus?.check_interval || 5}s
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip 
                label={`${activityData.activeLimits?.strike || 0} Strike Limits`}
                size="small"
                sx={{ bgcolor: 'rgba(59, 130, 246, 0.2)', color: '#3b82f6', fontSize: '0.7rem' }}
              />
              <Chip 
                label={`${activityData.activeLimits?.expiry || 0} Expiry Limits`}
                size="small"
                sx={{ bgcolor: 'rgba(168, 85, 247, 0.2)', color: '#a855f7', fontSize: '0.7rem' }}
              />
            </Box>
          </Box>

          {/* Active Limits Summary */}
          {(activityData.strikeLimits?.length > 0 || activityData.expiryLimits?.length > 0) && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" sx={{ color: '#94a3b8', mb: 1 }}>
                ⚙️ Active Max Loss Limits
              </Typography>
              <Box sx={{ 
                display: 'flex', 
                flexWrap: 'wrap', 
                gap: 1,
                p: 1,
                borderRadius: 1,
                bgcolor: 'rgba(0, 0, 0, 0.2)'
              }}>
                {activityData.strikeLimits?.map((limit, idx) => (
                  <Chip 
                    key={`strike-${idx}`}
                    label={`${limit.symbol}: $${limit.max_loss}`}
                    size="small"
                    sx={{ 
                      bgcolor: 'rgba(59, 130, 246, 0.15)', 
                      color: '#60a5fa',
                      fontSize: '0.65rem'
                    }}
                  />
                ))}
                {activityData.expiryLimits?.map((limit, idx) => (
                  <Chip 
                    key={`expiry-${idx}`}
                    label={`Exp ${limit.expiry_code}: $${limit.max_loss}`}
                    size="small"
                    sx={{ 
                      bgcolor: 'rgba(168, 85, 247, 0.15)', 
                      color: '#c084fc',
                      fontSize: '0.65rem'
                    }}
                  />
                ))}
              </Box>
            </Box>
          )}

          <Divider sx={{ my: 2, borderColor: 'rgba(148, 163, 184, 0.2)' }} />

          {/* Activity Log */}
          <Typography variant="subtitle2" sx={{ color: '#94a3b8', mb: 1 }}>
            📋 Real-Time Activity ({activityData.events?.length || 0} events)
          </Typography>
          
          <Box 
            sx={{ 
              maxHeight: 400, 
              overflow: 'auto',
              bgcolor: 'rgba(0, 0, 0, 0.3)',
              borderRadius: 1,
              p: 1
            }}
          >
            {activityData.events?.length === 0 ? (
              <Typography variant="body2" sx={{ color: '#64748b', textAlign: 'center', py: 4 }}>
                No monitoring activity yet. Set up max loss limits to see activity here.
              </Typography>
            ) : (
              activityData.events?.map((event, idx) => (
                <Box 
                  key={idx}
                  sx={{ 
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 1.5,
                    p: 1,
                    mb: 0.5,
                    borderRadius: 1,
                    bgcolor: getEventBgColor(event.type),
                    borderLeft: `3px solid ${getEventColor(event.type)}`,
                    '&:hover': { bgcolor: 'rgba(148, 163, 184, 0.1)' }
                  }}
                >
                  <Box sx={{ mt: 0.3 }}>
                    {getEventIcon(event.type)}
                  </Box>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                      <Typography 
                        variant="body2" 
                        sx={{ 
                          color: getEventColor(event.type),
                          fontWeight: event.type === 'breach' || event.type === 'warning' ? 600 : 400,
                          wordBreak: 'break-word'
                        }}
                      >
                        {event.message}
                      </Typography>
                    </Box>
                    {event.details && Object.keys(event.details).length > 0 && (
                      <Box sx={{ display: 'flex', gap: 1, mt: 0.5, flexWrap: 'wrap' }}>
                        {event.details.symbol && (
                          <Chip 
                            label={event.details.symbol} 
                            size="small" 
                            sx={{ bgcolor: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', fontSize: '0.6rem', height: 18 }}
                          />
                        )}
                        {event.details.loss_pct !== undefined && (
                          <Chip 
                            label={`${event.details.loss_pct}%`} 
                            size="small" 
                            sx={{ 
                              bgcolor: event.details.loss_pct >= 80 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(251, 191, 36, 0.2)', 
                              color: event.details.loss_pct >= 80 ? '#ef4444' : '#fbbf24',
                              fontSize: '0.6rem',
                              height: 18
                            }}
                          />
                        )}
                        {event.details.actual_loss !== undefined && (
                          <Chip 
                            label={`Loss: $${event.details.actual_loss.toFixed(2)}`} 
                            size="small" 
                            sx={{ bgcolor: 'rgba(239, 68, 68, 0.15)', color: '#f87171', fontSize: '0.6rem', height: 18 }}
                          />
                        )}
                      </Box>
                    )}
                    <Typography variant="caption" sx={{ color: '#64748b', display: 'block', mt: 0.5 }}>
                      {event.timestamp}
                    </Typography>
                  </Box>
                </Box>
              ))
            )}
          </Box>

          {/* Last Update */}
          <Typography variant="caption" sx={{ color: '#64748b', mt: 2, display: 'block', textAlign: 'right' }}>
            Last updated: {activityData.timestamp}
          </Typography>
        </>
      )}

      {/* No Data State */}
      {!activityData && !loading && !error && (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <MonitorHeartIcon sx={{ fontSize: 48, color: '#475569', mb: 2 }} />
          <Typography variant="body2" sx={{ color: '#64748b' }}>
            Loading monitoring activity...
          </Typography>
        </Box>
      )}
    </Paper>
  );
}
