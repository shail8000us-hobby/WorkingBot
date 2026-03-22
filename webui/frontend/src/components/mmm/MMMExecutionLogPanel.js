/**
 * MMMExecutionLogPanel — Pre-Fill Execution Event Log
 *
 * Displays execution intent events for an MMM session:
 *   ORDER_INTENT       — logged before placement (amber)
 *   ORDER_CONFIRMED    — logged after confirmed fill (green)
 *   EXIT_ROUND_START   — logged at start of each exit round (blue)
 *   EXIT_ROUND_END     — logged at end of each exit round (blue)
 *
 * Shows orphan warning when any ORDER_INTENT has no matching ORDER_CONFIRMED.
 *
 * Created: 2026-03-21
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  Box, Typography, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Chip, IconButton, Tooltip, CircularProgress,
  Alert, Paper,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import mmmService from './mmmService';

// =============================================================================
// Helpers
// =============================================================================

const fmtTs = (ts) => {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleTimeString('en-IN', { hour12: false });
  } catch (_) { return ts; }
};

const fmtDate = (ts) => {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
      + ' ' + new Date(ts).toLocaleTimeString('en-IN', { hour12: false });
  } catch (_) { return ts; }
};

const EVENT_COLOR = {
  ORDER_INTENT:    { color: '#ff9800', bg: 'rgba(255,152,0,0.12)',   label: 'INTENT' },
  ORDER_CONFIRMED: { color: '#4caf50', bg: 'rgba(76,175,80,0.12)',   label: 'CONFIRMED' },
  EXIT_ROUND_START:{ color: '#42a5f5', bg: 'rgba(66,165,245,0.12)', label: 'EXIT START' },
  EXIT_ROUND_END:  { color: '#42a5f5', bg: 'rgba(66,165,245,0.12)', label: 'EXIT END' },
};

const MonoCell = ({ children, color }) => (
  <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.78rem', color: color || 'text.primary', py: 0.5, px: 1 }}>
    {children}
  </TableCell>
);

const HeaderCell = ({ children }) => (
  <TableCell sx={{ fontWeight: 700, fontSize: '0.72rem', color: 'text.secondary', py: 0.75, px: 1, whiteSpace: 'nowrap' }}>
    {children}
  </TableCell>
);

// Detect orphans: ORDER_INTENT with no matching ORDER_CONFIRMED within 90s
function detectOrphans(events) {
  const intents = events.filter(e => e.event_type === 'ORDER_INTENT');
  const confirms = events.filter(e => e.event_type === 'ORDER_CONFIRMED');
  return intents.filter(intent => {
    const intentAt = new Date(intent.created_at).getTime();
    const matched = confirms.some(c => {
      const confirmAt = new Date(c.created_at).getTime();
      const delta = (confirmAt - intentAt) / 1000;
      return delta >= 0 && delta <= 90;
    });
    return !matched;
  });
}

// Format details object for display
function fmtDetails(details) {
  if (!details) return '—';
  try {
    const d = typeof details === 'string' ? JSON.parse(details) : details;
    const parts = [];
    if (d.side)   parts.push(d.side.toUpperCase());
    if (d.strike) parts.push(`@${d.strike}`);
    if (d.lots)   parts.push(`${d.lots}L`);
    if (d.mechanism) parts.push(d.mechanism);
    if (d.round_num != null) parts.push(`Round ${d.round_num}`);
    if (d.positions_to_close != null) parts.push(`${d.positions_to_close} pos`);
    if (d.closed_count != null) parts.push(`${d.closed_count} closed`);
    if (d.fill_price != null) parts.push(`fill=$${d.fill_price}`);
    return parts.join(' · ') || JSON.stringify(d);
  } catch (_) {
    return String(details);
  }
}

// =============================================================================
// Main component
// =============================================================================

export default function MMMExecutionLogPanel({ sessionId }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const load = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const res = await mmmService.getExecutionEvents(sessionId, 100);
      setData(res);
      setError(null);
    } catch (e) {
      setError(e.message || 'Failed to load execution events');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => { load(); }, [load]);

  const events   = data?.events || [];
  const orphans  = detectOrphans(events);

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Execution Event Log
          {data && (
            <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
              ({data.count} events)
            </Typography>
          )}
        </Typography>
        <Tooltip title="Refresh">
          <IconButton size="small" onClick={load} disabled={loading}>
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Orphan warning */}
      {orphans.length > 0 && (
        <Alert severity="warning" sx={{ mb: 1.5, py: 0.5 }}>
          {orphans.length} unconfirmed intent{orphans.length > 1 ? 's' : ''} detected —
          order may have been placed but confirmation was not recorded before last restart.
        </Alert>
      )}

      {/* Loading / error states */}
      {loading && !data && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress size={28} />
        </Box>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>
      )}

      {/* Empty state */}
      {!loading && !error && events.length === 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
          No execution events recorded for this session.
        </Typography>
      )}

      {/* Table */}
      {events.length > 0 && (
        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 1 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <HeaderCell>Time</HeaderCell>
                <HeaderCell>Type</HeaderCell>
                <HeaderCell>Details</HeaderCell>
                <HeaderCell>Remark</HeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {events.map((ev, idx) => {
                const cfg = EVENT_COLOR[ev.event_type] || { color: '#9e9e9e', bg: 'transparent', label: ev.event_type };
                const isOrphan = orphans.some(o => o.id === ev.id);
                return (
                  <TableRow
                    key={ev.id || idx}
                    sx={{ bgcolor: isOrphan ? 'rgba(255,152,0,0.06)' : 'transparent' }}
                  >
                    <MonoCell color="text.secondary">{fmtDate(ev.created_at)}</MonoCell>
                    <TableCell sx={{ py: 0.5, px: 1 }}>
                      <Chip
                        size="small"
                        label={cfg.label}
                        sx={{
                          bgcolor: cfg.bg,
                          color: cfg.color,
                          fontSize: '0.65rem',
                          fontWeight: 700,
                          height: 18,
                          '& .MuiChip-label': { px: 0.75 },
                        }}
                      />
                      {isOrphan && (
                        <Chip size="small" label="ORPHAN"
                          sx={{ ml: 0.5, bgcolor: 'rgba(255,152,0,0.2)', color: '#ff9800', fontSize: '0.6rem', height: 16, '& .MuiChip-label': { px: 0.5 } }} />
                      )}
                    </TableCell>
                    <MonoCell>{fmtDetails(ev.details)}</MonoCell>
                    <MonoCell color="text.secondary" sx={{ fontSize: '0.7rem', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {ev.remark || '—'}
                    </MonoCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
