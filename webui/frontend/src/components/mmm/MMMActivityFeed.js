/**
 * MMM Activity Feed — Background Activities Panel
 *
 * Shows real-time background activity log so users can see what the algo
 * is doing behind the scenes: order placement, fill waits, repricing,
 * errors, heartbeats, adjustments, etc.
 *
 * Provides full transparency into algo operations.
 *
 * Created: February 15, 2026
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Collapse,
  Badge,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  Circle as DotIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  HourglassEmpty as ProgressIcon,
} from '@mui/icons-material';
import mmmService from './mmmService';

// =============================================================================
// Severity styling
// =============================================================================

const SEVERITY_CONFIG = {
  info: {
    color: '#2196f3',
    bg: 'rgba(33,150,243,0.08)',
    Icon: InfoIcon,
    label: 'Info',
  },
  success: {
    color: '#4caf50',
    bg: 'rgba(76,175,80,0.10)',
    Icon: SuccessIcon,
    label: 'Success',
  },
  warning: {
    color: '#ff9800',
    bg: 'rgba(255,152,0,0.10)',
    Icon: WarningIcon,
    label: 'Warning',
  },
  error: {
    color: '#f44336',
    bg: 'rgba(244,67,54,0.10)',
    Icon: ErrorIcon,
    label: 'Error',
  },
  progress: {
    color: '#9c27b0',
    bg: 'rgba(156,39,176,0.08)',
    Icon: ProgressIcon,
    label: 'In Progress',
  },
};

const getSeverityConfig = (severity) =>
  SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.info;

// =============================================================================
// Time ago helper
// =============================================================================

function timeAgo(timestamp) {
  if (!timestamp) return '';
  const now = new Date();
  const then = new Date(timestamp + 'Z'); // UTC
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.floor(diffHr / 24)}d ago`;
}

// =============================================================================
// Single Activity Item
// =============================================================================

const ActivityItem = React.memo(({ activity }) => {
  const cfg = getSeverityConfig(activity.severity);
  const SeverityIcon = cfg.Icon;

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 1,
        py: 0.75,
        px: 1.5,
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        bgcolor: cfg.bg,
        '&:hover': { bgcolor: 'rgba(255,255,255,0.04)' },
        alignItems: 'flex-start',
      }}
    >
      <SeverityIcon
        sx={{
          fontSize: 16,
          color: cfg.color,
          mt: 0.3,
          flexShrink: 0,
          ...(activity.severity === 'progress' && {
            animation: 'spin 2s linear infinite',
            '@keyframes spin': {
              '0%': { transform: 'rotate(0deg)' },
              '100%': { transform: 'rotate(360deg)' },
            },
          }),
        }}
      />

      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          variant="body2"
          sx={{
            color: '#e0e0e0',
            fontSize: '0.82rem',
            lineHeight: 1.4,
            wordBreak: 'break-word',
          }}
        >
          {activity.message}
        </Typography>

        <Box sx={{ display: 'flex', gap: 1, mt: 0.25, alignItems: 'center' }}>
          {activity.session_id && (
            <Typography
              variant="caption"
              sx={{
                color: 'rgba(255,255,255,0.35)',
                fontFamily: 'monospace',
                fontSize: '0.82rem',
              }}
            >
              {activity.session_id}
            </Typography>
          )}
          <Tooltip
            title={
              activity.timestamp
                ? new Date(activity.timestamp + 'Z').toLocaleString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                  hour12: true,
                })
                : ''
            }
            placement="top"
          >
            <Typography
              variant="caption"
              sx={{
                color: 'rgba(255,255,255,0.3)',
                fontSize: '0.82rem',
                cursor: 'help',
              }}
            >
              {timeAgo(activity.timestamp)}
            </Typography>
          </Tooltip>
        </Box>
      </Box>
    </Box>
  );
});

ActivityItem.displayName = 'ActivityItem';

// =============================================================================
// Main Component
// =============================================================================

export default function MMMActivityFeed({ sessionId = null, socket = null }) {
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(true);
  const [newCount, setNewCount] = useState(0);
  const activitiesRef = useRef(activities);
  activitiesRef.current = activities;

  // Fetch activities from API
  const fetchActivities = useCallback(async () => {
    try {
      const result = await mmmService.getActivities(50, sessionId);
      if (result.success) {
        setActivities(result.activities || []);
        setNewCount(0);
      }
    } catch (err) {
      console.error('Failed to fetch activities:', err);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  // Initial load + polling
  useEffect(() => {
    fetchActivities();
    const interval = setInterval(fetchActivities, 5000);
    return () => clearInterval(interval);
  }, [fetchActivities]);

  // WebSocket real-time updates
  useEffect(() => {
    if (!socket) return;

    const handleActivity = (data) => {
      if (sessionId && data.session_id && data.session_id !== sessionId) return;

      setActivities((prev) => {
        const updated = [data, ...prev].slice(0, 100);
        return updated;
      });

      if (!expanded) {
        setNewCount((c) => c + 1);
      }
    };

    const handleSessionDeleted = (data) => {
      // A session was deleted — refetch activities to remove orphaned items
      fetchActivities();
    };

    const handleActivitiesUpdated = () => {
      // Progress activities were cleared — refetch to update display
      fetchActivities();
    };

    socket.on('mmm_activity', handleActivity);
    socket.on('mmm_session_deleted', handleSessionDeleted);
    socket.on('mmm_activities_updated', handleActivitiesUpdated);
    return () => {
      socket.off('mmm_activity', handleActivity);
      socket.off('mmm_session_deleted', handleSessionDeleted);
      socket.off('mmm_activities_updated', handleActivitiesUpdated);
    };
  }, [socket, sessionId, expanded, fetchActivities]);

  // Clear new count when expanding
  useEffect(() => {
    if (expanded) setNewCount(0);
  }, [expanded]);

  // Filter stale activities when no specific session is selected
  const displayedActivities = useMemo(() => {
    if (sessionId) {
      // Showing activities for a specific session - show all
      return activities;
    }
    // No session selected - only show recent activities (last 30 min) to avoid clutter from deleted sessions
    const thirtyMinutesAgo = new Date(Date.now() - 30 * 60 * 1000);
    return activities.filter((a) => {
      if (!a.timestamp) return true; // Keep if no timestamp
      try {
        const activityTime = new Date(a.timestamp + 'Z'); // UTC
        return activityTime > thirtyMinutesAgo;
      } catch {
        return true; // Keep if parse fails
      }
    });
  }, [activities, sessionId]);

  const errorCount = displayedActivities.filter((a) => a.severity === 'error').length;
  const warningCount = displayedActivities.filter((a) => a.severity === 'warning').length;
  const progressCount = displayedActivities.filter((a) => a.severity === 'progress').length;

  return (
    <Paper
      sx={{
        bgcolor: 'rgba(18,18,18,0.95)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 2,
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 1,
          bgcolor: 'rgba(255,255,255,0.03)',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          cursor: 'pointer',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle2" sx={{ color: '#e0e0e0', fontWeight: 600 }}>
            Background Activities
          </Typography>

          {progressCount > 0 && (
            <Chip
              size="small"
              icon={<CircularProgress size={10} sx={{ color: '#9c27b0' }} />}
              label={`${progressCount} pending`}
              sx={{
                height: 20,
                fontSize: '0.82rem',
                bgcolor: 'rgba(156,39,176,0.15)',
                color: '#ce93d8',
                '& .MuiChip-icon': { ml: 0.5 },
              }}
            />
          )}

          {warningCount > 0 && (
            <Chip
              size="small"
              icon={<WarningIcon sx={{ fontSize: 12 }} />}
              label={`${warningCount} warning${warningCount > 1 ? 's' : ''}`}
              sx={{
                height: 20,
                fontSize: '0.82rem',
                bgcolor: 'rgba(255,152,0,0.15)',
                color: '#ffcc80',
              }}
            />
          )}

          {errorCount > 0 && (
            <Chip
              size="small"
              icon={<ErrorIcon sx={{ fontSize: 12 }} />}
              label={`${errorCount} error${errorCount > 1 ? 's' : ''}`}
              sx={{
                height: 20,
                fontSize: '0.82rem',
                bgcolor: 'rgba(244,67,54,0.15)',
                color: '#ef9a9a',
              }}
            />
          )}
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Badge badgeContent={newCount} color="primary" max={99}>
            <Tooltip title="Refresh">
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  fetchActivities();
                }}
                sx={{ color: 'rgba(255,255,255,0.5)' }}
              >
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Badge>

          {expanded ? (
            <CollapseIcon fontSize="small" sx={{ color: 'rgba(255,255,255,0.4)' }} />
          ) : (
            <ExpandIcon fontSize="small" sx={{ color: 'rgba(255,255,255,0.4)' }} />
          )}
        </Box>
      </Box>

      {/* Activity List */}
      <Collapse in={expanded}>
        <Box
          sx={{
            maxHeight: 300,
            overflowY: 'auto',
            '&::-webkit-scrollbar': { width: 4 },
            '&::-webkit-scrollbar-thumb': {
              bgcolor: 'rgba(255,255,255,0.15)',
              borderRadius: 2,
            },
          }}
        >
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <CircularProgress size={24} />
            </Box>
          ) : displayedActivities.length === 0 ? (
            <Box sx={{ py: 3, textAlign: 'center' }}>
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.3)' }}>
                No background activities yet. Start a session to see real-time updates.
              </Typography>
            </Box>
          ) : (
            displayedActivities.map((activity, idx) => (
              <ActivityItem key={activity.id || idx} activity={activity} />
            ))
          )}
        </Box>
      </Collapse>
    </Paper>
  );
}
