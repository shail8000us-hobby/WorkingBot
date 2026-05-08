/**
 * Options Activity Panel
 * ======================
 * Real-time monitoring of background options trading activities
 * Shows max loss monitoring, warnings, position checks, and auto-close actions
 * 
 * Created: January 31, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';
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
  Button,
  ButtonGroup,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ErrorIcon from '@mui/icons-material/Error';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PlayCircleIcon from '@mui/icons-material/PlayCircle';
import DownloadIcon from '@mui/icons-material/Download';

// Filter definitions — maps UI label to the `category` field on events
const FILTER_TABS = [
  { label: 'All',    value: 'all' },
  { label: 'Trades', value: 'trade' },
  { label: 'Hedges', value: 'hedge' },
  { label: 'Alerts', value: 'alert' },
  { label: 'Errors', value: 'error' },
  { label: 'System', value: 'system' },
];

// Derive a single health object from monitorStatus + activeLimits.
// Prefers the backend-computed health when available; falls back to client logic
// so the banner still works if the backend hasn't restarted with the new field.
function computeHealth(monitorStatus, activeLimits) {
  if (!monitorStatus) return { level: 'stopped', reason: 'Monitor not initialised', color: '#ef4444', bg: 'rgba(239,68,68,0.2)' };

  // Use backend-computed health when present (monitor was restarted with new code)
  if (monitorStatus.health) {
    const { level, reason } = monitorStatus.health;
    const color = level === 'healthy' ? '#22c55e' : level === 'degraded' ? '#f59e0b' : '#ef4444';
    const bg = level === 'healthy' ? 'rgba(34,197,94,0.2)' : level === 'degraded' ? 'rgba(245,158,11,0.2)' : 'rgba(239,68,68,0.2)';
    return { level, reason, color, bg };
  }

  // Legacy fallback (backend not yet restarted)
  const { running, eval_count, skipped_stale, secs_since_eval } = monitorStatus;
  const hasLimits = (activeLimits?.strike || 0) + (activeLimits?.expiry || 0) > 0;
  if (!running)       return { level: 'stopped',  reason: 'Monitor thread is not running',                  color: '#ef4444', bg: 'rgba(239,68,68,0.2)' };
  if (!hasLimits)     return { level: 'healthy',  reason: 'No limits configured',                           color: '#22c55e', bg: 'rgba(34,197,94,0.2)' };
  if (!eval_count)    return { level: 'degraded', reason: 'Running but no evaluations — cache may be stale', color: '#f59e0b', bg: 'rgba(245,158,11,0.2)' };
  if (secs_since_eval > 30) return { level: 'degraded', reason: `Last eval ${secs_since_eval}s ago`,        color: '#f59e0b', bg: 'rgba(245,158,11,0.2)' };
  return { level: 'healthy', reason: 'Checking every 5s', color: '#22c55e', bg: 'rgba(34,197,94,0.2)' };
}

export default function OptionsActivityPanel({ refreshTrigger = 0 }) {
  const [activityData, setActivityData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const [activeFilter, setActiveFilter] = useState('all');

  // Filter events client-side by category field
  const filteredEvents = useCallback((events) => {
    if (!events) return [];
    if (activeFilter === 'all') return events;
    return events.filter(e => (e.category || 'system') === activeFilter);
  }, [activeFilter]);

  const handleExportCsv = () => {
    window.open('/api/options/monitoring-activity/export', '_blank');
  };

  // Fetch monitoring activity
  const fetchActivity = useCallback(async () => {
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
  }, []);

  // Auto-refresh every 10 seconds — pauses when tab is hidden
  useVisibilityAwarePolling(fetchActivity, 10000, 60000);

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
      case 'pnl_fallback':
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
      case 'pnl_fallback':
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
      case 'pnl_fallback':
        return 'rgba(245, 158, 11, 0.15)';
      case 'check_start':
      case 'position_check':
        return 'rgba(59, 130, 246, 0.1)';
      default:
        return 'transparent';
    }
  };

  if (!expanded) {
    const h = computeHealth(activityData?.monitorStatus, activityData?.activeLimits);
    const secsAgo = activityData?.monitorStatus?.secs_since_eval;
    return (
      <Paper sx={{ p: 1.5, bgcolor: 'rgba(15, 23, 42, 0.8)', border: `1px solid ${h.level === 'stopped' ? 'rgba(239,68,68,0.5)' : h.level === 'degraded' ? 'rgba(245,158,11,0.4)' : 'rgba(34,197,94,0.3)'}` }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 0.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <MonitorHeartIcon sx={{ fontSize: '1rem', color: h.color }} />
            <Typography variant="subtitle2" sx={{ color: h.color, fontWeight: 600, fontSize: '0.75rem' }}>
              Max Loss Monitor
            </Typography>
            {activityData && (
              <Chip
                label={h.level === 'healthy' ? `✓ Healthy` : h.level === 'degraded' ? `⚠ Degraded` : `✗ Stopped`}
                size="small"
                sx={{ bgcolor: h.bg, color: h.color, fontWeight: 700, fontSize: '0.65rem' }}
              />
            )}
          </Box>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            {activityData && (
              <>
                {h.level !== 'healthy' && (
                  <Typography variant="caption" sx={{ color: h.color, fontWeight: 600, fontSize: '0.65rem', maxWidth: 220 }}>
                    {h.reason}
                  </Typography>
                )}
                {secsAgo != null && (
                  <Typography variant="caption" sx={{ color: '#64748b', fontSize: '0.62rem' }}>
                    checked {secsAgo}s ago
                  </Typography>
                )}
                <Chip
                  label={`${activityData.activeLimits?.strike || 0}S + ${activityData.activeLimits?.expiry || 0}E`}
                  size="small"
                  sx={{ bgcolor: 'rgba(59, 130, 246, 0.2)', color: '#3b82f6', fontSize: '0.65rem' }}
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
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
              {(() => {
                const h = computeHealth(activityData.monitorStatus, activityData.activeLimits);
                const chipIcon = h.level === 'healthy'
                  ? <PlayCircleIcon sx={{ color: `${h.color} !important` }} />
                  : <ErrorIcon sx={{ color: `${h.color} !important` }} />;
                const chipLabel = h.level === 'healthy' ? '✓ Healthy'
                  : h.level === 'degraded' ? '⚠ Degraded'
                  : '✗ Stopped';
                return (
                  <>
                    <Chip
                      icon={chipIcon}
                      label={chipLabel}
                      size="small"
                      sx={{ bgcolor: h.bg, color: h.color, fontWeight: 700 }}
                    />
                    {h.level !== 'healthy' && (
                      <Typography variant="caption" sx={{ color: h.color, fontWeight: 600 }}>
                        {h.reason}
                      </Typography>
                    )}
                  </>
                );
              })()}
              <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                Loops: {activityData.monitorStatus?.check_count || 0}
              </Typography>
              <Typography variant="caption" sx={{
                color: (activityData.monitorStatus?.eval_count || 0) === 0 && ((activityData.activeLimits?.strike || 0) + (activityData.activeLimits?.expiry || 0)) > 0
                  ? '#f59e0b' : '#94a3b8',
                fontWeight: (activityData.monitorStatus?.eval_count || 0) === 0 && ((activityData.activeLimits?.strike || 0) + (activityData.activeLimits?.expiry || 0)) > 0
                  ? 700 : 400
              }}>
                Evals: {activityData.monitorStatus?.eval_count || 0}
                {activityData.monitorStatus?.secs_since_eval != null && (
                  <span style={{ color: '#64748b', fontWeight: 400 }}> · last {activityData.monitorStatus.secs_since_eval}s ago</span>
                )}
              </Typography>
              {(activityData.monitorStatus?.skipped_stale || 0) > 0 && (
                <Typography variant="caption" sx={{ color: '#f59e0b', fontWeight: 700 }}>
                  ⚠️ Skipped (stale): {activityData.monitorStatus.skipped_stale}
                </Typography>
              )}
              {(activityData.monitorStatus?.pnl_fallback_symbols?.length || 0) > 0 && (
                <Typography variant="caption" sx={{ color: '#f59e0b', fontWeight: 700 }}>
                  ⚠️ Fallback PnL: {activityData.monitorStatus.pnl_fallback_symbols.join(', ')}
                </Typography>
              )}
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

          {/* Filter Bar + Export */}
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5, flexWrap: 'wrap', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="subtitle2" sx={{ color: '#94a3b8', mr: 0.5 }}>
                Filter:
              </Typography>
              <ButtonGroup size="small" variant="outlined">
                {FILTER_TABS.map(tab => (
                  <Button
                    key={tab.value}
                    onClick={() => setActiveFilter(tab.value)}
                    sx={{
                      fontSize: '0.65rem',
                      px: 1,
                      py: 0.3,
                      borderColor: 'rgba(148,163,184,0.3)',
                      color: activeFilter === tab.value ? '#e2e8f0' : '#64748b',
                      bgcolor: activeFilter === tab.value ? 'rgba(59,130,246,0.25)' : 'transparent',
                      '&:hover': { bgcolor: 'rgba(59,130,246,0.15)', borderColor: 'rgba(148,163,184,0.5)' },
                    }}
                  >
                    {tab.label}
                  </Button>
                ))}
              </ButtonGroup>
            </Box>
            <Tooltip title="Export last 24h as CSV">
              <Button
                size="small"
                startIcon={<DownloadIcon sx={{ fontSize: '0.9rem' }} />}
                onClick={handleExportCsv}
                sx={{
                  fontSize: '0.65rem',
                  color: '#94a3b8',
                  borderColor: 'rgba(148,163,184,0.3)',
                  '&:hover': { borderColor: '#94a3b8', color: '#e2e8f0' },
                }}
                variant="outlined"
              >
                Export CSV
              </Button>
            </Tooltip>
          </Box>

          {/* Activity Log */}
          {(() => {
            const visibleEvents = filteredEvents(activityData.events);
            return (
              <Typography variant="subtitle2" sx={{ color: '#94a3b8', mb: 1 }}>
                Real-Time Activity ({visibleEvents.length}{activeFilter !== 'all' ? ` of ${activityData.events?.length || 0}` : ''} events)
              </Typography>
            );
          })()}

          <Box
            sx={{
              maxHeight: 400,
              overflow: 'auto',
              bgcolor: 'rgba(0, 0, 0, 0.3)',
              borderRadius: 1,
              p: 1
            }}
          >
            {filteredEvents(activityData.events).length === 0 ? (
              <Typography variant="body2" sx={{ color: '#64748b', textAlign: 'center', py: 4 }}>
                {activeFilter === 'all'
                  ? 'No monitoring activity yet. Set up max loss limits to see activity here.'
                  : `No "${activeFilter}" events in recent log.`}
              </Typography>
            ) : (
              filteredEvents(activityData.events).map((event, idx) => (
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
                          fontWeight: event.type === 'breach' || event.type === 'warning' || event.type === 'pnl_fallback' ? 600 : 400,
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

          {/* Hedge History */}
          {activityData.hedgeEvents?.length > 0 && (
            <>
              <Divider sx={{ my: 2, borderColor: 'rgba(148, 163, 184, 0.2)' }} />
              <Typography variant="subtitle2" sx={{ color: '#94a3b8', mb: 1 }}>
                ⚡ Hedge History ({activityData.hedgeEvents.length})
              </Typography>
              <Box
                sx={{
                  maxHeight: 300,
                  overflow: 'auto',
                  bgcolor: 'rgba(0, 0, 0, 0.3)',
                  borderRadius: 1,
                  p: 1,
                }}
              >
                {activityData.hedgeEvents.map((evt, idx) => (
                  <Box
                    key={idx}
                    sx={{
                      p: 1,
                      mb: 0.5,
                      borderRadius: 1,
                      borderLeft: `3px solid ${evt.trigger === 'auto' ? '#f59e0b' : '#3b82f6'}`,
                      bgcolor: evt.trigger === 'auto'
                        ? 'rgba(245, 158, 11, 0.08)'
                        : 'rgba(59, 130, 246, 0.08)',
                    }}
                  >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Chip
                        size="small"
                        label={evt.trigger === 'auto' ? '[AUTO HEDGE]' : '[MANUAL HEDGE]'}
                        sx={{
                          height: 18,
                          fontSize: '0.6rem',
                          bgcolor: evt.trigger === 'auto'
                            ? 'rgba(245, 158, 11, 0.2)'
                            : 'rgba(59, 130, 246, 0.2)',
                          color: evt.trigger === 'auto' ? '#f59e0b' : '#3b82f6',
                        }}
                      />
                      <Typography variant="caption" sx={{ color: '#64748b' }}>
                        {evt.timestamp}
                      </Typography>
                    </Box>
                    <Typography variant="body2" sx={{ color: '#e2e8f0' }}>
                      {evt.side === 'sell' ? 'SOLD' : 'BOUGHT'} {evt.size} BTC-PERP
                      {' '}@ {evt.order_type === 'smart' ? 'Smart' : 'Market'}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#94a3b8', display: 'block' }}>
                      Pre-hedge Δ: {evt.pre_delta > 0 ? '+' : ''}{evt.pre_delta}
                      {' '}→ Post-hedge Δ: ~{evt.post_delta}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#64748b' }}>
                      Order ID: #{evt.order_id} ✅
                    </Typography>
                  </Box>
                ))}
              </Box>
            </>
          )}

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
