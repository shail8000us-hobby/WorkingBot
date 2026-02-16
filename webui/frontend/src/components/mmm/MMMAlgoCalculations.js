/**
 * MMMAlgoCalculations — Money Mind & Method
 *
 * Live walk-through of the algorithm's execution, showing every
 * calculation at each heartbeat in Section 16 style.
 *
 * Displays: entry state, trigger checks, reversal detection,
 * loss formulas, lots calculation, strike shifts, close-at-5,
 * and running P&L — all with IST timestamps.
 *
 * Maps to MONEY_POWER_CALCULATION_LOGIC.md §16 (Complete Walk-Through)
 *
 * Created: February 15, 2026
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Switch,
  FormControlLabel,
  Divider,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import VerticalAlignBottomIcon from '@mui/icons-material/VerticalAlignBottom';
import mmmService from './mmmService';

// ─────────────────────────────────────────────────────────────────────────────
// Color scheme for different entry types
// ─────────────────────────────────────────────────────────────────────────────
const TYPE_COLORS = {
  entry: { bg: '#1a237e', border: '#3f51b5', label: 'ENTRY', chip: '#3f51b5' },
  standard: { bg: '#1b5e20', border: '#4caf50', label: 'STANDARD', chip: '#4caf50' },
  reversal_skip: { bg: '#e65100', border: '#ff9800', label: 'REV SKIP', chip: '#ff9800' },
  first_reversal: { bg: '#b71c1c', border: '#f44336', label: 'REVERSAL', chip: '#f44336' },
  continuation: { bg: '#1b5e20', border: '#66bb6a', label: 'CONTINUE', chip: '#66bb6a' },
  shift: { bg: '#4a148c', border: '#9c27b0', label: 'SHIFT', chip: '#9c27b0' },
  close_at_5: { bg: '#004d40', border: '#26a69a', label: 'CLOSE@5', chip: '#26a69a' },
  none: { bg: '#263238', border: '#546e7a', label: 'NO TRIGGER', chip: '#546e7a' },
  both_sides_up: { bg: '#e65100', border: '#ff6d00', label: 'BOTH SIDES', chip: '#ff6d00' },
  safety: { bg: '#880e4f', border: '#e91e63', label: 'SAFETY', chip: '#e91e63' },
};

function getTypeStyle(entry) {
  if (!entry) return TYPE_COLORS.none;
  const t = entry.type || 'none';
  return TYPE_COLORS[t] || TYPE_COLORS.none;
}

// ─────────────────────────────────────────────────────────────────────────────
// Single walkthrough entry card
// ─────────────────────────────────────────────────────────────────────────────
const WalkthroughEntry = ({ entry, index }) => {
  const style = getTypeStyle(entry);

  if (!entry) return null;

  return (
    <Paper
      elevation={2}
      sx={{
        mb: 1.5,
        border: `1px solid ${style.border}`,
        bgcolor: style.bg + '20',
        overflow: 'hidden',
      }}
    >
      {/* Header bar */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 1.5,
          py: 0.5,
          bgcolor: style.bg + '40',
          borderBottom: `1px solid ${style.border}30`,
        }}
      >
        <Chip
          label={style.label}
          size="small"
          sx={{
            bgcolor: style.chip,
            color: '#fff',
            fontWeight: 700,
            fontSize: '0.7rem',
            height: 22,
          }}
        />
        <Typography
          variant="caption"
          sx={{ color: '#90caf9', fontFamily: 'monospace' }}
        >
          {entry.label || ''} {entry.summary ? `— ${entry.summary}` : ''}
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Typography
          variant="caption"
          sx={{ color: '#b0bec5', fontFamily: 'monospace', fontSize: '0.7rem' }}
        >
          {entry.timestamp_ist || ''}
        </Typography>
      </Box>

      {/* Body — preformatted walkthrough text */}
      <Box
        sx={{
          px: 1.5,
          py: 1,
          fontFamily: '"Fira Code", "Cascadia Code", "JetBrains Mono", "Consolas", monospace',
          fontSize: '0.78rem',
          lineHeight: 1.6,
          color: '#e0e0e0',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          overflowX: 'auto',
        }}
      >
        {renderLines(buildLines(entry))}
      </Box>
    </Paper>
  );
};

/**
 * Build display lines from entry data.
 * Combines calculation (trigger checks) and details (outcome + formulas).
 */
function buildLines(entry) {
  const lines = [];
  if (entry.calculation) {
    // calculation is a newline-separated string
    lines.push('── Trigger Check ──');
    lines.push(...entry.calculation.split('\n'));
  }
  if (entry.details && entry.details.length > 0) {
    lines.push(...entry.details);
  }
  return lines.length > 0 ? lines : ['(no calculation data)'];
}

/**
 * Render lines with simple syntax highlighting
 */
function renderLines(lines) {
  return lines.map((line, i) => {
    // Section headers (lines starting with ─ or ═ or >>)
    if (
      line.startsWith('─') ||
      line.startsWith('═') ||
      line.startsWith('>>')
    ) {
      return (
        <div key={i} style={{ color: '#64b5f6', fontWeight: 600 }}>
          {line}
        </div>
      );
    }

    // Result lines (YES/NO, TRIGGERED, SKIP, etc.)
    if (
      line.includes('→ YES') ||
      line.includes('TRIGGERED') ||
      line.includes('SELL ') ||
      line.includes('EXECUTED')
    ) {
      return (
        <div key={i} style={{ color: '#69f0ae' }}>
          {highlightNumbers(line)}
        </div>
      );
    }

    if (
      line.includes('→ NO') ||
      line.includes('SKIP') ||
      line.includes('DO NOTHING') ||
      line.includes('No action')
    ) {
      return (
        <div key={i} style={{ color: '#ffab40' }}>
          {highlightNumbers(line)}
        </div>
      );
    }

    // Warning/error lines
    if (line.includes('⚠') || line.includes('❌') || line.includes('BLOCKED')) {
      return (
        <div key={i} style={{ color: '#ff5252' }}>
          {line}
        </div>
      );
    }

    // Success lines
    if (line.includes('✓') || line.includes('✅')) {
      return (
        <div key={i} style={{ color: '#69f0ae' }}>
          {line}
        </div>
      );
    }

    // Indented calculation lines
    if (line.startsWith('  ')) {
      return (
        <div key={i} style={{ color: '#b0bec5' }}>
          {highlightNumbers(line)}
        </div>
      );
    }

    // Default
    return (
      <div key={i}>
        {highlightNumbers(line)}
      </div>
    );
  });
}

/**
 * Highlight numbers and dollar amounts in calculation lines
 */
function highlightNumbers(text) {
  // Split on numbers/dollar amounts, keeping them for highlighting
  const parts = text.split(/(\$[\d,.]+|\b\d+\.?\d*\b)/g);
  return parts.map((part, i) => {
    if (/^\$/.test(part)) {
      return (
        <span key={i} style={{ color: '#ffd54f', fontWeight: 600 }}>
          {part}
        </span>
      );
    }
    if (/^\d+\.?\d*$/.test(part) && part.length > 0) {
      return (
        <span key={i} style={{ color: '#81d4fa' }}>
          {part}
        </span>
      );
    }
    return part;
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export default function MMMAlgoCalculations({ session, wsData }) {
  const [walkthrough, setWalkthrough] = useState([]);
  const [loading, setLoading] = useState(true);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef(null);
  const bottomRef = useRef(null);

  const sessionId = session?.session_id;

  // Fetch initial walkthrough from API
  const fetchWalkthrough = useCallback(async () => {
    if (!sessionId) return;
    try {
      setLoading(true);
      const resp = await mmmService.getWalkthrough(sessionId);
      if (resp.success && resp.walkthrough) {
        setWalkthrough(resp.walkthrough);
      }
    } catch (err) {
      console.error('Failed to fetch walkthrough:', err);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchWalkthrough();
  }, [fetchWalkthrough]);

  // Append new entries from WebSocket
  useEffect(() => {
    if (wsData?.walkthroughEntries?.length > 0) {
      setWalkthrough((prev) => {
        // Merge: avoid duplicates by checking heartbeat number
        const existing = new Set(prev.map((e) => e.heartbeat));
        const newEntries = wsData.walkthroughEntries.filter(
          (e) => !existing.has(e.heartbeat)
        );
        if (newEntries.length === 0) return prev;
        const merged = [...prev, ...newEntries];
        // Keep last 200
        return merged.slice(-200);
      });
    }
  }, [wsData?.walkthroughEntries]);

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [walkthrough, autoScroll]);

  if (!session) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">No session selected</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 1 }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 1.5,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle1" fontWeight={700}>
            Algo Calculations
          </Typography>
          <Chip
            label={`${walkthrough.length} entries`}
            size="small"
            color="primary"
            variant="outlined"
          />
          <Typography variant="caption" color="text.secondary">
            (Section 16 Walk-Through • IST)
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FormControlLabel
            control={
              <Switch
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                size="small"
              />
            }
            label={
              <Typography variant="caption">Auto-scroll</Typography>
            }
          />
          <Tooltip title="Scroll to latest">
            <IconButton
              size="small"
              onClick={() =>
                bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
              }
            >
              <VerticalAlignBottomIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Refresh from server">
            <IconButton size="small" onClick={fetchWalkthrough}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Divider sx={{ mb: 1.5 }} />

      {/* Legend */}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1.5 }}>
        {Object.entries(TYPE_COLORS).map(([key, val]) => (
          <Chip
            key={key}
            label={val.label}
            size="small"
            sx={{
              bgcolor: val.chip + '30',
              color: val.chip,
              border: `1px solid ${val.chip}50`,
              fontSize: '0.78rem',
              height: 20,
            }}
          />
        ))}
      </Box>

      {/* Walkthrough entries */}
      <Box
        ref={scrollRef}
        sx={{
          maxHeight: 'calc(100vh - 380px)',
          overflowY: 'auto',
          overflowX: 'hidden',
          pr: 0.5,
          // Custom scrollbar
          '&::-webkit-scrollbar': { width: 6 },
          '&::-webkit-scrollbar-thumb': {
            bgcolor: '#546e7a',
            borderRadius: 3,
          },
        }}
      >
        {loading ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <CircularProgress size={32} />
            <Typography
              variant="caption"
              display="block"
              color="text.secondary"
              mt={1}
            >
              Loading walkthrough...
            </Typography>
          </Box>
        ) : walkthrough.length === 0 ? (
          <Paper
            sx={{
              p: 3,
              textAlign: 'center',
              bgcolor: '#263238',
              border: '1px dashed #546e7a',
            }}
          >
            <Typography color="text.secondary">
              No walkthrough entries yet.
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Entries will appear after the first heartbeat runs.
            </Typography>
          </Paper>
        ) : (
          walkthrough.map((entry, idx) => (
            <WalkthroughEntry key={entry.heartbeat ?? idx} entry={entry} index={idx} />
          ))
        )}
        <div ref={bottomRef} />
      </Box>
    </Box>
  );
}
