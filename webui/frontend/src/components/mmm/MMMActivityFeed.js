/**
 * MMM Live Monitor & Activity Feed
 *
 * Two-section panel:
 * 1. LIVE STATUS — Real-time heartbeat dashboard (premiums, P&L, triggers,
 *    countdown to next beat, health grade, regime/margin/wind-down status)
 * 2. EVENT LOG — Only meaningful events (adjustments, fills, safety, errors)
 *    with category filtering. No more heartbeat noise.
 *
 * Receives structured data via `mmm_heartbeat_summary` WebSocket event.
 *
 * Created: February 15, 2026
 * Redesigned: February 23, 2026
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
  LinearProgress,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  HourglassEmpty as ProgressIcon,
  FiberManualRecord as DotIcon,
  ShoppingCart as OrderIcon,
  TrendingUp as AdjustIcon,
  Shield as SafetyIcon,
  Settings as SystemIcon,
  FavoriteBorder as HeartIcon,
} from '@mui/icons-material';
import mmmService from './mmmService';

// =============================================================================
// Constants
// =============================================================================

const SEVERITY_CONFIG = {
  info: { color: '#2196f3', bg: 'rgba(33,150,243,0.08)', Icon: InfoIcon },
  success: { color: '#4caf50', bg: 'rgba(76,175,80,0.10)', Icon: SuccessIcon },
  warning: { color: '#ff9800', bg: 'rgba(255,152,0,0.10)', Icon: WarningIcon },
  error: { color: '#f44336', bg: 'rgba(244,67,54,0.10)', Icon: ErrorIcon },
  progress: { color: '#9c27b0', bg: 'rgba(156,39,176,0.08)', Icon: ProgressIcon },
};

const CATEGORY_CONFIG = {
  all: { label: 'All', Icon: null, color: '#90a4ae' },
  orders: { label: 'Orders', Icon: OrderIcon, color: '#29b6f6' },
  adjustments: { label: 'Trades', Icon: AdjustIcon, color: '#ab47bc' },
  safety: { label: 'Safety', Icon: SafetyIcon, color: '#ff9800' },
  system: { label: 'System', Icon: SystemIcon, color: '#78909c' },
};

const getSeverityConfig = (sev) => SEVERITY_CONFIG[sev] || SEVERITY_CONFIG.info;

// =============================================================================
// Helpers
// =============================================================================

function parseTS(ts) {
  if (!ts) return null;
  try {
    const d = (ts.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(ts))
      ? new Date(ts) : new Date(ts + 'Z');
    return isNaN(d.getTime()) ? null : d;
  } catch { return null; }
}

function timeAgo(timestamp) {
  const d = parseTS(timestamp);
  if (!d) return '';
  const sec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (sec < 5) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

function formatCountdown(targetIso) {
  const target = parseTS(targetIso);
  if (!target) return null;
  const remaining = Math.max(0, Math.floor((target.getTime() - Date.now()) / 1000));
  if (remaining <= 0) return '0s';
  const m = Math.floor(remaining / 60);
  const s = remaining % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function pnlColor(val) {
  if (val > 0) return '#4caf50';
  if (val < 0) return '#f44336';
  return '#9e9e9e';
}

function tierColor(tier) {
  const map = { GREEN: '#4caf50', YELLOW: '#ffeb3b', ORANGE: '#ff9800', RED: '#f44336', CRITICAL: '#d50000' };
  return map[tier] || '#4caf50';
}

function regimeColor(action) {
  if (!action || action === 'NORMAL') return '#4caf50';
  if (action.includes('BLOCK')) return '#f44336';
  if (action.includes('WARN')) return '#ff9800';
  return '#ff9800';
}

// =============================================================================
// Live Heartbeat Status Panel
// =============================================================================

const LiveStatus = React.memo(({ summary }) => {
  const [countdown, setCountdown] = useState(null);

  // Countdown timer — ticks every second
  useEffect(() => {
    if (!summary?.next_heartbeat) return;
    const tick = () => setCountdown(formatCountdown(summary.next_heartbeat));
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, [summary?.next_heartbeat]);

  if (!summary) {
    return (
      <Box sx={{ px: 2, py: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
        <HeartIcon sx={{ fontSize: 16, color: 'rgba(255,255,255,0.3)' }} />
        <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.4)', fontStyle: 'italic' }}>
          Waiting for first heartbeat...
        </Typography>
      </Box>
    );
  }

  const s = summary;
  const triggerMax = s.min_trigger_pct || 3;
  const cePct = Math.min(100, Math.max(0, (Math.abs(s.ce_trigger_pct || 0) / triggerMax) * 100));
  const pePct = Math.min(100, Math.max(0, (Math.abs(s.pe_trigger_pct || 0) / triggerMax) * 100));
  const ceTriggered = Math.abs(s.ce_trigger_pct || 0) >= triggerMax;
  const peTriggered = Math.abs(s.pe_trigger_pct || 0) >= triggerMax;

  const statusColor = {
    RUNNING: '#4caf50', PAUSED: '#ff9800', STOPPED: '#f44336',
    BOTH_SIDES_UP: '#ff5722', IDLE: '#9e9e9e',
  }[s.status] || '#9e9e9e';

  return (
    <Box sx={{ px: 1.5, py: 1 }}>
      {/* Row 1: Status + Beat + Grade + Countdown */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75, flexWrap: 'wrap' }}>
        <Chip
          size="small"
          icon={<DotIcon sx={{ fontSize: '10px !important', color: `${statusColor} !important` }} />}
          label={s.status || 'UNKNOWN'}
          sx={{
            height: 22, fontSize: '0.78rem', fontWeight: 700,
            bgcolor: `${statusColor}22`, color: statusColor,
            '& .MuiChip-icon': { ml: 0.5 },
          }}
        />
        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', fontFamily: 'monospace', fontSize: '0.78rem' }}>
          Beat #{s.heartbeat_num}
        </Typography>
        <Chip
          size="small"
          label={`${s.health_grade || '?'}`}
          sx={{
            height: 18, fontSize: '0.72rem', fontWeight: 700, minWidth: 22,
            bgcolor: s.health_grade === 'A' ? 'rgba(76,175,80,0.2)' :
              s.health_grade === 'B' ? 'rgba(139,195,74,0.2)' :
              s.health_grade === 'C' ? 'rgba(255,152,0,0.2)' : 'rgba(244,67,54,0.2)',
            color: s.health_grade === 'A' ? '#4caf50' :
              s.health_grade === 'B' ? '#8bc34a' :
              s.health_grade === 'C' ? '#ff9800' : '#f44336',
          }}
        />
        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.35)', fontSize: '0.75rem' }}>
          {s.latency_ms?.toFixed(0)}ms
        </Typography>

        <Box sx={{ flex: 1 }} />

        {countdown !== null && (
          <Tooltip title={`Next heartbeat in ${countdown}. Interval: ${s.next_interval}s${s.adaptive_tier ? ` (${s.adaptive_tier})` : ''}`}>
            <Typography variant="caption" sx={{
              color: '#4fc3f7', fontWeight: 600, fontFamily: 'monospace', fontSize: '0.82rem',
              bgcolor: 'rgba(79,195,247,0.08)', px: 0.75, py: 0.15, borderRadius: 1,
            }}>
              ⏱ {countdown}
            </Typography>
          </Tooltip>
        )}
      </Box>

      {/* Row 2: Premiums + Trigger Bars */}
      <Box sx={{ display: 'flex', gap: 2, mb: 0.75 }}>
        {/* CE side */}
        <Box sx={{ flex: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.25 }}>
            <Typography variant="caption" sx={{ color: '#ef5350', fontWeight: 600, fontSize: '0.78rem' }}>
              CE {s.ce_strike ? Math.round(s.ce_strike) : '—'}
            </Typography>
            <Typography variant="caption" sx={{ color: '#e0e0e0', fontFamily: 'monospace', fontSize: '0.78rem' }}>
              ${(s.ce_premium || 0).toFixed(2)}
            </Typography>
          </Box>
          <Tooltip title={`CE trigger: ${(s.ce_trigger_pct || 0).toFixed(1)}% / ${triggerMax}%${ceTriggered ? ' — TRIGGERED!' : ''}`}>
            <LinearProgress
              variant="determinate"
              value={cePct}
              sx={{
                height: 5, borderRadius: 2,
                bgcolor: 'rgba(255,255,255,0.06)',
                '& .MuiLinearProgress-bar': {
                  bgcolor: ceTriggered ? '#f44336' : cePct > 60 ? '#ff9800' : '#4caf50',
                  borderRadius: 2,
                  transition: 'transform 0.4s ease',
                },
              }}
            />
          </Tooltip>
          <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.7rem' }}>
            {(s.ce_trigger_pct || 0).toFixed(1)}% / {triggerMax}% · {s.ce_total_lots || 0} lots
          </Typography>
        </Box>

        {/* PE side */}
        <Box sx={{ flex: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.25 }}>
            <Typography variant="caption" sx={{ color: '#66bb6a', fontWeight: 600, fontSize: '0.78rem' }}>
              PE {s.pe_strike ? Math.round(s.pe_strike) : '—'}
            </Typography>
            <Typography variant="caption" sx={{ color: '#e0e0e0', fontFamily: 'monospace', fontSize: '0.78rem' }}>
              ${(s.pe_premium || 0).toFixed(2)}
            </Typography>
          </Box>
          <Tooltip title={`PE trigger: ${(s.pe_trigger_pct || 0).toFixed(1)}% / ${triggerMax}%${peTriggered ? ' — TRIGGERED!' : ''}`}>
            <LinearProgress
              variant="determinate"
              value={pePct}
              sx={{
                height: 5, borderRadius: 2,
                bgcolor: 'rgba(255,255,255,0.06)',
                '& .MuiLinearProgress-bar': {
                  bgcolor: peTriggered ? '#f44336' : pePct > 60 ? '#ff9800' : '#4caf50',
                  borderRadius: 2,
                  transition: 'transform 0.4s ease',
                },
              }}
            />
          </Tooltip>
          <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.7rem' }}>
            {(s.pe_trigger_pct || 0).toFixed(1)}% / {triggerMax}% · {s.pe_total_lots || 0} lots
          </Typography>
        </Box>
      </Box>

      {/* Row 3: P&L + Status Indicators */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
        <Tooltip title={`Realized: $${(s.realized_pnl || 0).toFixed(2)} · Unrealized: $${(s.unrealized_pnl || 0).toFixed(2)} · Fees: $${(s.fees || 0).toFixed(2)}`}>
          <Typography variant="caption" sx={{
            color: pnlColor(s.net_pnl || 0), fontWeight: 700, fontFamily: 'monospace', fontSize: '0.85rem',
          }}>
            P&L: {(s.net_pnl || 0) >= 0 ? '+' : ''}${(s.net_pnl || 0).toFixed(2)}
          </Typography>
        </Tooltip>

        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.35)', fontSize: '0.72rem' }}>
          Δ {(s.portfolio_delta || 0) >= 0 ? '+' : ''}{(s.portfolio_delta || 0).toFixed(3)}
        </Typography>

        {s.adjustment_count > 0 && (
          <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.35)', fontSize: '0.72rem' }}>
            Adj: {s.adjustment_count}
          </Typography>
        )}

        <Box sx={{ flex: 1 }} />

        {/* Status pills */}
        {s.wind_down_active && (
          <Chip size="small" label="WIND-DOWN" sx={{
            height: 18, fontSize: '0.68rem', fontWeight: 700,
            bgcolor: 'rgba(156,39,176,0.2)', color: '#ce93d8',
          }} />
        )}
        {s.regime_action && s.regime_action !== 'NORMAL' && (
          <Chip size="small" label={`REGIME: ${s.regime_action}`} sx={{
            height: 18, fontSize: '0.68rem', fontWeight: 700,
            bgcolor: `${regimeColor(s.regime_action)}22`, color: regimeColor(s.regime_action),
          }} />
        )}
        {s.margin_tier && s.margin_tier !== 'GREEN' && (
          <Chip size="small" label={`MARGIN: ${s.margin_tier}`} sx={{
            height: 18, fontSize: '0.68rem', fontWeight: 700,
            bgcolor: `${tierColor(s.margin_tier)}22`, color: tierColor(s.margin_tier),
          }} />
        )}
        {s.circuit_state && s.circuit_state !== 'CLOSED' && (
          <Chip size="small" label={`CIRCUIT: ${s.circuit_state}`} sx={{
            height: 18, fontSize: '0.68rem', fontWeight: 700,
            bgcolor: 'rgba(244,67,54,0.2)', color: '#ef9a9a',
          }} />
        )}
      </Box>
    </Box>
  );
});

LiveStatus.displayName = 'LiveStatus';

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
        borderBottom: '1px solid rgba(255,255,255,0.03)',
        bgcolor: cfg.bg,
        '&:hover': { bgcolor: 'rgba(255,255,255,0.04)' },
        alignItems: 'flex-start',
      }}
    >
      <SeverityIcon
        sx={{
          fontSize: 14,
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
        <Box sx={{ display: 'flex', gap: 1, mt: 0.15, alignItems: 'center' }}>
          {activity.category && activity.category !== 'system' && (
            <Chip
              size="small"
              label={CATEGORY_CONFIG[activity.category]?.label || activity.category}
              sx={{
                height: 16, fontSize: '0.65rem',
                bgcolor: 'rgba(255,255,255,0.06)', color: CATEGORY_CONFIG[activity.category]?.color || '#90a4ae',
              }}
            />
          )}
          {activity.session_id && (
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.25)', fontFamily: 'monospace', fontSize: '0.72rem' }}>
              {activity.session_id}
            </Typography>
          )}
          <Tooltip
            title={(() => {
              const d = parseTS(activity.timestamp);
              return d ? d.toLocaleString('en-US', {
                month: 'short', day: 'numeric', hour: '2-digit',
                minute: '2-digit', second: '2-digit', hour12: true,
              }) : '';
            })()}
            placement="top"
          >
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.25)', fontSize: '0.72rem', cursor: 'help' }}>
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
  const [activeFilter, setActiveFilter] = useState('all');
  const [heartbeatSummary, setHeartbeatSummary] = useState(null);
  const listRef = useRef(null);

  // Fetch activities from API
  const fetchActivities = useCallback(async () => {
    try {
      const result = await mmmService.getActivities(80, sessionId);
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

  // Initial load + reduced polling (summary handles real-time now)
  useEffect(() => {
    fetchActivities();
    const interval = setInterval(fetchActivities, 30000);
    return () => clearInterval(interval);
  }, [fetchActivities]);

  // WebSocket: real-time activity events
  useEffect(() => {
    if (!socket) return;

    const handleActivity = (data) => {
      if (sessionId && data.session_id && data.session_id !== sessionId) return;
      setActivities((prev) => [data, ...prev].slice(0, 120));
      if (!expanded) setNewCount((c) => c + 1);
    };

    const handleHeartbeatSummary = (data) => {
      if (sessionId && data.session_id && data.session_id !== sessionId) return;
      setHeartbeatSummary(data);
    };

    const handleSessionDeleted = () => fetchActivities();
    const handleActivitiesUpdated = () => fetchActivities();

    socket.on('mmm_activity', handleActivity);
    socket.on('mmm_heartbeat_summary', handleHeartbeatSummary);
    socket.on('mmm_session_deleted', handleSessionDeleted);
    socket.on('mmm_activities_updated', handleActivitiesUpdated);

    return () => {
      socket.off('mmm_activity', handleActivity);
      socket.off('mmm_heartbeat_summary', handleHeartbeatSummary);
      socket.off('mmm_session_deleted', handleSessionDeleted);
      socket.off('mmm_activities_updated', handleActivitiesUpdated);
    };
  }, [socket, sessionId, expanded, fetchActivities]);

  // Clear new count when expanding
  useEffect(() => {
    if (expanded) setNewCount(0);
  }, [expanded]);

  // Filter activities by time + category
  const displayedActivities = useMemo(() => {
    let items = activities;

    // Time filter: show last 60 min when no session selected
    if (!sessionId) {
      const cutoff = new Date(Date.now() - 60 * 60 * 1000);
      items = items.filter((a) => {
        const d = parseTS(a.timestamp);
        return !d || d > cutoff;
      });
    }

    // Category filter
    if (activeFilter !== 'all') {
      items = items.filter((a) => a.category === activeFilter);
    }

    return items;
  }, [activities, sessionId, activeFilter]);

  const errorCount = activities.filter((a) => a.severity === 'error').length;
  const warningCount = activities.filter((a) => a.severity === 'warning').length;

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
          py: 0.75,
          bgcolor: 'rgba(255,255,255,0.03)',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          cursor: 'pointer',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <HeartIcon sx={{ fontSize: 16, color: heartbeatSummary ? '#4caf50' : 'rgba(255,255,255,0.3)',
            animation: heartbeatSummary ? 'pulse 2s ease-in-out infinite' : 'none',
            '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.4 } },
          }} />
          <Typography variant="subtitle2" sx={{ color: '#e0e0e0', fontWeight: 600, fontSize: '0.88rem' }}>
            Live Monitor
          </Typography>
          {warningCount > 0 && (
            <Chip size="small" icon={<WarningIcon sx={{ fontSize: '12px !important' }} />}
              label={warningCount}
              sx={{ height: 18, fontSize: '0.72rem', bgcolor: 'rgba(255,152,0,0.15)', color: '#ffcc80' }}
            />
          )}
          {errorCount > 0 && (
            <Chip size="small" icon={<ErrorIcon sx={{ fontSize: '12px !important' }} />}
              label={errorCount}
              sx={{ height: 18, fontSize: '0.72rem', bgcolor: 'rgba(244,67,54,0.15)', color: '#ef9a9a' }}
            />
          )}
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Badge badgeContent={newCount} color="primary" max={99}>
            <Tooltip title="Refresh">
              <IconButton size="small" onClick={(e) => { e.stopPropagation(); fetchActivities(); }}
                sx={{ color: 'rgba(255,255,255,0.5)' }}
              >
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Badge>
          {expanded
            ? <CollapseIcon fontSize="small" sx={{ color: 'rgba(255,255,255,0.4)' }} />
            : <ExpandIcon fontSize="small" sx={{ color: 'rgba(255,255,255,0.4)' }} />
          }
        </Box>
      </Box>

      <Collapse in={expanded}>
        {/* Live Status Section */}
        <Box sx={{ borderBottom: '1px solid rgba(255,255,255,0.06)', bgcolor: 'rgba(255,255,255,0.015)' }}>
          <LiveStatus summary={heartbeatSummary} />
        </Box>

        {/* Category Filter Chips */}
        <Box sx={{
          display: 'flex', gap: 0.5, px: 1.5, py: 0.75,
          borderBottom: '1px solid rgba(255,255,255,0.04)',
          bgcolor: 'rgba(255,255,255,0.01)',
        }}>
          {Object.entries(CATEGORY_CONFIG).map(([key, cfg]) => (
            <Chip
              key={key}
              size="small"
              label={cfg.label}
              onClick={() => setActiveFilter(key)}
              sx={{
                height: 22, fontSize: '0.72rem', cursor: 'pointer',
                bgcolor: activeFilter === key ? `${cfg.color}22` : 'transparent',
                color: activeFilter === key ? cfg.color : 'rgba(255,255,255,0.4)',
                border: activeFilter === key ? `1px solid ${cfg.color}44` : '1px solid rgba(255,255,255,0.08)',
                fontWeight: activeFilter === key ? 700 : 400,
                '&:hover': { bgcolor: `${cfg.color}15` },
              }}
            />
          ))}
        </Box>

        {/* Activity List */}
        <Box
          ref={listRef}
          sx={{
            maxHeight: 240,
            overflowY: 'auto',
            '&::-webkit-scrollbar': { width: 4 },
            '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(255,255,255,0.12)', borderRadius: 2 },
          }}
        >
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <CircularProgress size={20} />
            </Box>
          ) : displayedActivities.length === 0 ? (
            <Box sx={{ py: 2.5, textAlign: 'center' }}>
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.82rem' }}>
                {activeFilter !== 'all'
                  ? `No ${CATEGORY_CONFIG[activeFilter]?.label.toLowerCase() || ''} events yet`
                  : 'No events yet. Start a session to see activity.'}
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
