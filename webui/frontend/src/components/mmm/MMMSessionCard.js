/**
 * MMMSessionCard — Money Mind & Method
 *
 * Card view for each session with summary stats:
 * - Status, mode, created time
 * - CE/PE strikes + lots
 * - P&L summary
 * - Quick action buttons (start/pause/stop/delete)
 *
 * Created: February 15, 2026
 */

import React from 'react';
import {
  Box,
  Card,
  CardContent,
  CardActions,
  Typography,
  Chip,
  Grid,
  IconButton,
  Tooltip,
  Divider,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  Delete as DeleteIcon,
  Circle as CircleIcon,
  OpenInNew as OpenIcon,
} from '@mui/icons-material';

const STATUS_COLORS = {
  RUNNING: '#4caf50',
  PAUSED: '#ff9800',
  BOTH_SIDES_UP: '#f44336',
  STOPPED: '#757575',
  IDLE: '#9e9e9e',
  ERROR: '#f44336',
};

function formatDate(iso) {
  if (!iso) return '--';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
           ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  } catch { return '--'; }
}

function pnlColor(v) {
  if (v > 0) return '#4caf50';
  if (v < 0) return '#f44336';
  return 'text.secondary';
}

function StatBox({ label, value, color }) {
  return (
    <Box sx={{ textAlign: 'center' }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        sx={{ fontWeight: 600, fontFamily: 'monospace', color: color || 'text.primary' }}
      >
        {value}
      </Typography>
    </Box>
  );
}

export default function MMMSessionCard({
  session,
  onSelect,
  onStart,
  onPause,
  onResume,
  onStop,
  onDelete,
}) {
  if (!session) return null;

  const status = session.strategy_status || session.status || 'IDLE';
  const statusColor = STATUS_COLORS[status] || STATUS_COLORS.IDLE;
  const sid = session.session_id || '';

  const ceStrike = session.ce?.active_strike || session.ce_strike || 0;
  const peStrike = session.pe?.active_strike || session.pe_strike || 0;
  const ceLots = session.ce?.active_lots || session.ce_active_lots || 0;
  const peLots = session.pe?.active_lots || session.pe_active_lots || 0;

  const realized = session.realized_pnl || 0;
  const unrealized = session.unrealized_pnl || 0;
  const fees = session.total_fees || 0;
  // Use pre-computed net_pnl when available (authoritative); fall back to R+U-F.
  const netPnl = session.net_pnl ?? (realized + unrealized - fees);
  const adjCount = session.adjustment_count || 0;

  const isRunning = status === 'RUNNING';
  const isPaused = status === 'PAUSED' || status === 'BOTH_SIDES_UP';
  const isStopped = status === 'STOPPED';
  const isIdle = status === 'IDLE';

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 2,
        borderColor: `${statusColor}50`,
        cursor: onSelect ? 'pointer' : 'default',
        transition: 'transform 0.15s, box-shadow 0.15s',
        '&:hover': onSelect ? {
          transform: 'translateY(-2px)',
          boxShadow: `0 4px 12px ${statusColor}20`,
        } : {},
      }}
      onClick={() => onSelect?.(session)}
    >
      <CardContent sx={{ pb: 1 }}>
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Chip
              icon={<CircleIcon sx={{ fontSize: 8 }} />}
              label={status}
              size="small"
              sx={{
                bgcolor: `${statusColor}15`,
                color: statusColor,
                fontWeight: 700,
                fontSize: '0.78rem',
                '& .MuiChip-icon': { color: statusColor },
              }}
            />
            <Typography variant="caption" color="text.secondary">
              {sid}
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary">
            {formatDate(session.created_at)}
          </Typography>
        </Box>

        {/* Strikes */}
        <Box sx={{ display: 'flex', gap: 2, mb: 1.5 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">CE</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
              {ceStrike > 0 ? Number(ceStrike).toLocaleString() : '—'}
              {ceLots > 0 && (
                <Typography component="span" variant="caption" color="text.secondary"> ({ceLots}L)</Typography>
              )}
            </Typography>
          </Box>
          <Divider orientation="vertical" flexItem />
          <Box>
            <Typography variant="caption" color="text.secondary">PE</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
              {peStrike > 0 ? Number(peStrike).toLocaleString() : '—'}
              {peLots > 0 && (
                <Typography component="span" variant="caption" color="text.secondary"> ({peLots}L)</Typography>
              )}
            </Typography>
          </Box>
        </Box>

        {/* Stats row */}
        <Grid container spacing={1}>
          <Grid item xs={3}>
            <StatBox label="Net P&L" value={`$${netPnl.toFixed(0)}`} color={pnlColor(netPnl)} />
          </Grid>
          <Grid item xs={3}>
            <StatBox label="Realized" value={`$${realized.toFixed(0)}`} color={pnlColor(realized)} />
          </Grid>
          <Grid item xs={3}>
            <StatBox label="Unrealized" value={`$${unrealized.toFixed(0)}`} color={pnlColor(unrealized)} />
          </Grid>
          <Grid item xs={3}>
            <StatBox label="Adj" value={adjCount} />
          </Grid>
        </Grid>
      </CardContent>

      <CardActions sx={{ px: 2, pb: 1.5, justifyContent: 'flex-end' }}>
        {isIdle && onStart && (
          <Tooltip title="Start">
            <IconButton size="small" color="success" onClick={(e) => { e.stopPropagation(); onStart(sid); }}>
              <PlayIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        {isRunning && onPause && (
          <Tooltip title="Pause">
            <IconButton size="small" color="warning" onClick={(e) => { e.stopPropagation(); onPause(sid); }}>
              <PauseIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        {isPaused && onResume && (
          <Tooltip title="Resume">
            <IconButton size="small" color="success" onClick={(e) => { e.stopPropagation(); onResume(sid); }}>
              <PlayIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        {(isRunning || isPaused) && onStop && (
          <Tooltip title="Stop">
            <IconButton size="small" color="error" onClick={(e) => { e.stopPropagation(); onStop(sid); }}>
              <StopIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        {(isIdle || isStopped) && onDelete && (
          <Tooltip title="Delete">
            <IconButton size="small" onClick={(e) => { e.stopPropagation(); onDelete(sid); }}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        {onSelect && (
          <Tooltip title="Open">
            <IconButton size="small" onClick={(e) => { e.stopPropagation(); onSelect(session); }}>
              <OpenIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </CardActions>
    </Card>
  );
}
