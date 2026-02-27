/**
 * MMMAlgoCalculations — Money Mind & Method
 *
 * Live walk-through of the algorithm's execution, showing every
 * calculation at each heartbeat (Section 16 style).
 *
 * Enhanced Feb 26, 2026:
 *  - Collapsible entry cards (click header to toggle)
 *  - Filter chips — click type to filter; multi-select = OR; "Clear" resets
 *  - Full-text search box across calculation + detail lines
 *  - Stats bar showing net P&L, realized, total premium, adj count,
 *    last aggressor, CE/PE lots from latest entry's state field
 *  - Export button — downloads visible entries as .txt
 *  - Section-aware line coloring (Trigger=blue, Regime=orange, etc.)
 *  - Rich card headers: regime-action badge, margin-tier badge,
 *    wind-down badge, perp-hedge direction badge, adaptive-interval badge
 *  - New TYPE_COLORS: wind_down, regime_blocked
 *
 * Maps to MONEY_POWER_CALCULATION_LOGIC.md §16 (Complete Walk-Through)
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
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
  TextField,
  InputAdornment,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import VerticalAlignBottomIcon from '@mui/icons-material/VerticalAlignBottom';
import DownloadIcon from '@mui/icons-material/Download';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import mmmService from './mmmService';

// ─────────────────────────────────────────────────────────────────────────────
// Entry-type color scheme
// ─────────────────────────────────────────────────────────────────────────────
const TYPE_COLORS = {
  entry:                { bg: '#1a237e', border: '#3f51b5', label: 'ENTRY',      chip: '#3f51b5' },
  standard:             { bg: '#1b5e20', border: '#4caf50', label: 'STANDARD',   chip: '#4caf50' },
  reversal_skip:        { bg: '#e65100', border: '#ff9800', label: 'REV SKIP',   chip: '#ff9800' },
  first_reversal:       { bg: '#b71c1c', border: '#f44336', label: 'REVERSAL',   chip: '#f44336' },
  continuation:         { bg: '#1b5e20', border: '#66bb6a', label: 'CONTINUE',   chip: '#66bb6a' },
  shift:                { bg: '#4a148c', border: '#9c27b0', label: 'SHIFT',      chip: '#9c27b0' },
  close_at_5:           { bg: '#004d40', border: '#26a69a', label: 'CLOSE@5',    chip: '#26a69a' },
  none:                 { bg: '#263238', border: '#546e7a', label: 'NO TRIGGER', chip: '#546e7a' },
  both_sides_up:        { bg: '#e65100', border: '#ff6d00', label: 'BOTH SIDES', chip: '#ff6d00' },
  safety:               { bg: '#880e4f', border: '#e91e63', label: 'SAFETY',     chip: '#e91e63' },
  wind_down:            { bg: '#004d4d', border: '#00bcd4', label: 'WIND-DOWN',  chip: '#00bcd4' },
  regime_blocked:       { bg: '#3e2723', border: '#ff7043', label: 'REGIME BLK', chip: '#ff7043' },
};

// ─────────────────────────────────────────────────────────────────────────────
// Section-header color map  (lines that start with ── / ══)
// ─────────────────────────────────────────────────────────────────────────────
const SECTION_COLORS = {
  'Heartbeat Interval':  '#78909c',
  'Trigger Check':       '#64b5f6',
  'Reversal Check':      '#ffb74d',
  'Loss Calculation':    '#ef9a9a',
  'Strike Check':        '#ce93d8',
  'Lots Calculation':    '#80cbc4',
  'Execution':           '#a5d6a7',
  'Regime Controls':     '#ff8a65',
  'Margin Guardian':     '#f48fb1',
  'Perp Delta Hedge':    '#4dd0e1',
  'Wind-Down Mode':      '#4db6ac',
  'Close-at-5':          '#26a69a',
  'Safety Checks':       '#ff5252',
  'State After':         '#b0bec5',
};

function getSectionColor(line) {
  for (const [key, color] of Object.entries(SECTION_COLORS)) {
    if (line.includes(key)) return color;
  }
  return '#64b5f6';
}

function getTypeStyle(entry) {
  if (!entry) return TYPE_COLORS.none;
  return TYPE_COLORS[entry.type || 'none'] || TYPE_COLORS.none;
}

// ─────────────────────────────────────────────────────────────────────────────
// Badge helpers
// ─────────────────────────────────────────────────────────────────────────────
function regimeChipColor(action) {
  if (!action || action === 'NORMAL') return { bg: '#1b5e2060', color: '#4caf50' };
  if (action === 'WARN')              return { bg: '#e65100',   color: '#fff' };
  if (action.startsWith('BLOCK'))     return { bg: '#b71c1c',   color: '#fff' };
  if (action === 'FORCE_REDUCE')      return { bg: '#880e4f',   color: '#fff' };
  return { bg: '#546e7a', color: '#fff' };
}

function marginChipColor(tier) {
  const map = {
    GREEN:    { bg: '#1b5e20', color: '#4caf50' },
    YELLOW:   { bg: '#f57f17', color: '#fff' },
    ORANGE:   { bg: '#e65100', color: '#fff' },
    RED:      { bg: '#b71c1c', color: '#fff' },
    CRITICAL: { bg: '#880e4f', color: '#fff' },
  };
  return map[tier] || { bg: '#546e7a', color: '#fff' };
}

// ─────────────────────────────────────────────────────────────────────────────
// Syntax highlighting helpers
// ─────────────────────────────────────────────────────────────────────────────
function highlightNumbers(text) {
  const parts = text.split(/(\$[\d,.]+|\b\d+\.?\d*\b)/g);
  return parts.map((part, i) => {
    if (/^\$/.test(part))
      return <span key={i} style={{ color: '#ffd54f', fontWeight: 600 }}>{part}</span>;
    if (/^\d+\.?\d*$/.test(part) && part.length > 0)
      return <span key={i} style={{ color: '#81d4fa' }}>{part}</span>;
    return part;
  });
}

/**
 * Build ordered lines from an entry — calculation string first, then details array.
 */
function buildLines(entry) {
  const lines = [];
  if (entry.calculation) lines.push(...entry.calculation.split('\n'));
  if (entry.details && entry.details.length > 0) lines.push(...entry.details);
  return lines.length > 0 ? lines : ['(no calculation data)'];
}

/**
 * Render lines with section-aware and keyword-aware coloring.
 */
function renderLines(lines) {
  return lines.map((line, i) => {
    if (!line) return <div key={i} style={{ height: 6 }} />;

    // Section headers (── … ── or ══ … ══)
    if (line.startsWith('\u2500') || line.startsWith('\u2550') || line.startsWith('>>')) {
      return (
        <div key={i} style={{ color: getSectionColor(line), fontWeight: 700, marginTop: 4 }}>
          {line}
        </div>
      );
    }

    // Triggered / executed / YES
    if (
      line.includes('-> YES') || line.includes('\u2192 YES') ||
      line.includes('TRIGGERED') || line.includes('SELL ') ||
      line.includes('EXECUTED') || line.includes('\u2713')
    ) {
      return <div key={i} style={{ color: '#69f0ae' }}>{highlightNumbers(line)}</div>;
    }

    // Blocked / emergency / force reduce
    if (
      line.includes('BLOCKED') || line.includes('\u26d4') ||
      line.includes('EMERGENCY') || line.includes('FORCE_REDUCE') || line.includes('\u274c')
    ) {
      return <div key={i} style={{ color: '#ff5252', fontWeight: 600 }}>{line}</div>;
    }

    // Warning / paused
    if (line.includes('\u26a0') || line.includes('WARNING') || line.includes('PAUSED')) {
      return <div key={i} style={{ color: '#ffab40' }}>{highlightNumbers(line)}</div>;
    }

    // Skip / NO / do nothing
    if (
      line.includes('-> NO') || line.includes('\u2192 NO') ||
      line.includes('SKIP') || line.includes('DO NOTHING') ||
      line.includes('No action') || line.includes('No triggers')
    ) {
      return <div key={i} style={{ color: '#ffab40' }}>{highlightNumbers(line)}</div>;
    }

    // All-clear
    if (
      line.includes('All clear') || line.includes('pass \u2713') || line.includes('healthy \u2713')
    ) {
      return <div key={i} style={{ color: '#69f0ae' }}>{line}</div>;
    }

    // Indented calculation sub-lines
    if (line.startsWith('  ') || line.startsWith('\t')) {
      return <div key={i} style={{ color: '#b0bec5' }}>{highlightNumbers(line)}</div>;
    }

    return <div key={i}>{highlightNumbers(line)}</div>;
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Single walkthrough entry card  (collapsible)
// ─────────────────────────────────────────────────────────────────────────────
const WalkthroughEntry = ({ entry, index }) => {
  const style = getTypeStyle(entry);
  // Last entry (index 0 when reversed, but we render in order so index = last means high number)
  // Collapse all but the very last rendered entry
  const [collapsed, setCollapsed] = useState(index < 1 ? false : true);

  if (!entry) return null;

  const regimeInfo   = entry.regime;
  const marginInfo   = entry.margin;
  const perpInfo     = entry.perp_hedge;
  const regimeAction = regimeInfo?.action || 'NORMAL';
  const marginTier   = marginInfo?.tier   || 'GREEN';
  const adaptiveTier = entry.adaptive_tier;
  const intervalSec  = entry.interval;
  const windDown     = entry.wind_down_active;

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
      {/* ── Header (clickable to expand/collapse) ── */}
      <Box
        onClick={() => setCollapsed(c => !c)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          px: 1.5,
          py: 0.5,
          bgcolor: style.bg + '40',
          borderBottom: collapsed ? 'none' : `1px solid ${style.border}30`,
          cursor: 'pointer',
          '&:hover': { bgcolor: style.bg + '60' },
          flexWrap: 'wrap',
          userSelect: 'none',
        }}
      >
        {/* Type chip */}
        <Chip
          label={style.label}
          size="small"
          sx={{ bgcolor: style.chip, color: '#fff', fontWeight: 700, fontSize: '0.7rem', height: 22, flexShrink: 0 }}
        />

        {/* Summary text */}
        <Typography variant="caption" sx={{ color: '#90caf9', fontFamily: 'monospace', flexGrow: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {entry.label || ''}{entry.summary ? ` \u2014 ${entry.summary}` : ''}
        </Typography>

        {/* Regime badge (only when non-NORMAL) */}
        {regimeInfo && regimeAction !== 'NORMAL' && (() => {
          const rc = regimeChipColor(regimeAction);
          return (
            <Chip
              label={`REG:${regimeAction.replace('BLOCK_', 'BLK_')}`}
              size="small"
              sx={{ bgcolor: rc.bg, color: rc.color, fontSize: '0.65rem', height: 18, flexShrink: 0 }}
            />
          );
        })()}

        {/* Margin tier badge (only when non-GREEN) */}
        {marginInfo && marginTier !== 'GREEN' && (() => {
          const mc = marginChipColor(marginTier);
          return (
            <Chip
              label={`MRG:${marginTier} ${marginInfo.utilization_pct != null ? marginInfo.utilization_pct.toFixed(0) + '%' : ''}`}
              size="small"
              sx={{ bgcolor: mc.bg, color: mc.color, fontSize: '0.65rem', height: 18, flexShrink: 0 }}
            />
          );
        })()}

        {/* Wind-down badge */}
        {windDown && (
          <Chip
            label="WIND-DOWN"
            size="small"
            sx={{ bgcolor: '#004d4d', color: '#00bcd4', border: '1px solid #00bcd4', fontSize: '0.65rem', height: 18, flexShrink: 0 }}
          />
        )}

        {/* Perp hedge direction badge */}
        {perpInfo?.enabled && perpInfo.direction && perpInfo.direction !== 'FLAT' && (
          <Chip
            label={`PERP:${perpInfo.direction} ${perpInfo.lots}L`}
            size="small"
            sx={{ bgcolor: '#006064', color: '#4dd0e1', fontSize: '0.65rem', height: 18, flexShrink: 0 }}
          />
        )}

        {/* Adaptive interval badge */}
        {adaptiveTier && adaptiveTier !== 'manual' && (
          <Chip
            label={`${intervalSec}s/${adaptiveTier}`}
            size="small"
            sx={{ bgcolor: '#37474f', color: '#90a4ae', fontSize: '0.65rem', height: 18, flexShrink: 0 }}
          />
        )}

        {/* Timestamp */}
        <Typography variant="caption" sx={{ color: '#b0bec5', fontFamily: 'monospace', fontSize: '0.7rem', flexShrink: 0 }}>
          {entry.timestamp_ist || ''}
        </Typography>

        {/* Expand/collapse indicator */}
        <Typography variant="caption" sx={{ color: '#546e7a', fontSize: '0.65rem', flexShrink: 0 }}>
          {collapsed ? '\u25b6' : '\u25bc'}
        </Typography>
      </Box>

      {/* ── Body (walkthrough text) ── */}
      {!collapsed && (
        <Box
          sx={{
            px: 1.5,
            py: 1,
            fontFamily: '"Fira Code","Cascadia Code","JetBrains Mono","Consolas",monospace',
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
      )}
    </Paper>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────
export default function MMMAlgoCalculations({ session, wsData }) {
  const [walkthrough,   setWalkthrough]   = useState([]);
  const [loading,       setLoading]       = useState(true);
  const [autoScroll,    setAutoScroll]    = useState(true);
  const [activeFilters, setActiveFilters] = useState(new Set());
  const [searchText,    setSearchText]    = useState('');
  const scrollRef = useRef(null);
  const bottomRef = useRef(null);

  const sessionId = session?.session_id;

  // ── Fetch initial data from REST API ──
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

  useEffect(() => { fetchWalkthrough(); }, [fetchWalkthrough]);

  // ── Merge new WebSocket entries ──
  useEffect(() => {
    if (wsData?.walkthroughEntries?.length > 0) {
      setWalkthrough(prev => {
        const existing = new Set(prev.map(e => e.heartbeat));
        const newEntries = wsData.walkthroughEntries.filter(e => !existing.has(e.heartbeat));
        if (newEntries.length === 0) return prev;
        return [...prev, ...newEntries].slice(-200);
      });
    }
  }, [wsData?.walkthroughEntries]);

  // ── Auto-scroll ──
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [walkthrough, autoScroll]);

  // ── Filter toggle ──
  const toggleFilter = useCallback((type) => {
    setActiveFilters(prev => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type); else next.add(type);
      return next;
    });
  }, []);

  // ── Export to .txt ──
  const exportWalkthrough = useCallback(() => {
    const lines = [
      `MMM Algo Calculations Export \u2014 Session ${sessionId}`,
      `Exported: ${new Date().toISOString()}`,
      '='.repeat(80),
    ];
    walkthrough.forEach(entry => {
      lines.push('');
      lines.push(`[${entry.timestamp_ist || entry.timestamp}]  HB#${entry.heartbeat}  ${(entry.type||'').toUpperCase()}  ${entry.summary || ''}`);
      if (entry.calculation) lines.push(entry.calculation);
      if (entry.details)     lines.push(...entry.details);
      lines.push('-'.repeat(60));
    });
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `mmm_walkthrough_${sessionId}_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }, [walkthrough, sessionId]);

  // ── Filtered + searched entries (memoized) ──
  const visibleEntries = useMemo(() => {
    let result = walkthrough;
    if (activeFilters.size > 0) {
      result = result.filter(e => activeFilters.has(e.type || 'none'));
    }
    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      result = result.filter(e => {
        return [e.summary || '', e.calculation || '', ...(e.details || [])]
          .join(' ').toLowerCase().includes(q);
      });
    }
    return result;
  }, [walkthrough, activeFilters, searchText]);

  // ── Stats from last entry ──
  const lastEntry  = walkthrough[walkthrough.length - 1];
  const stats      = lastEntry?.state || {};
  const lastRegime = lastEntry?.regime;
  const lastMargin = lastEntry?.margin;

  // ─────────────────────────────────────────────────────────────────────────
  if (!session) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">No session selected</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 1 }}>

      {/* ── Header row ── */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1, flexWrap: 'wrap', gap: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle1" fontWeight={700}>Algo Calculations</Typography>
          <Chip
            label={`${walkthrough.length} total / ${visibleEntries.length} shown`}
            size="small" color="primary" variant="outlined"
          />
          <Typography variant="caption" color="text.secondary">(Walk-Through \u2022 IST)</Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <FormControlLabel
            control={<Switch checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} size="small" />}
            label={<Typography variant="caption">Auto-scroll</Typography>}
          />
          <Tooltip title="Scroll to latest">
            <IconButton size="small" onClick={() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' })}>
              <VerticalAlignBottomIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Export to text file">
            <IconButton size="small" onClick={exportWalkthrough}>
              <DownloadIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Refresh from server">
            <IconButton size="small" onClick={fetchWalkthrough}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* ── Stats bar (last entry) ── */}
      {lastEntry && (
        <Box sx={{ display: 'flex', gap: 1, mb: 1, flexWrap: 'wrap', p: 0.75, bgcolor: '#1a2327', borderRadius: 1, border: '1px solid #263238' }}>
          {[
            { label: 'Net P&L',      value: `$${(stats.net_pnl       || 0).toFixed(2)}`, color: (stats.net_pnl || 0) >= 0 ? '#69f0ae' : '#ff5252' },
            { label: 'Realized',     value: `$${(stats.realized       || 0).toFixed(2)}`, color: '#90caf9' },
            { label: 'Total Prem',   value: `${(stats.total_premium_btc || 0).toFixed(4)} BTC`, color: '#ffd54f' },
            { label: 'Adj Count',    value: stats.adjustment_count != null ? String(stats.adjustment_count) : '\u2014', color: '#ce93d8' },
            { label: 'Last Agg',     value: stats.last_aggressor || '\u2014', color: '#ff8a65' },
            { label: 'CE Lots',      value: stats.ce_total_lots  != null ? String(stats.ce_total_lots)  : '\u2014', color: '#64b5f6' },
            { label: 'PE Lots',      value: stats.pe_total_lots  != null ? String(stats.pe_total_lots)  : '\u2014', color: '#ef9a9a' },
            lastRegime && lastRegime.action !== 'NORMAL'
              ? { label: 'Regime', value: lastRegime.action, color: lastRegime.action.includes('BLOCK') ? '#ff5252' : '#ffab40' }
              : null,
            lastMargin && lastMargin.tier !== 'GREEN'
              ? { label: 'Margin', value: `${lastMargin.tier} ${lastMargin.utilization_pct != null ? lastMargin.utilization_pct.toFixed(0) + '%' : ''}`, color: lastMargin.tier === 'YELLOW' ? '#ffab40' : '#ff5252' }
              : null,
          ].filter(Boolean).map((stat, i) => (
            <Box key={i} sx={{ display: 'flex', flexDirection: 'column', minWidth: 68 }}>
              <Typography variant="caption" sx={{ color: '#546e7a', fontSize: '0.64rem' }}>{stat.label}</Typography>
              <Typography variant="caption" sx={{ color: stat.color, fontWeight: 700, fontFamily: 'monospace', fontSize: '0.78rem' }}>{stat.value}</Typography>
            </Box>
          ))}
        </Box>
      )}

      <Divider sx={{ mb: 1 }} />

      {/* ── Filter chips (click = toggle; active = solid) ── */}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
        {Object.entries(TYPE_COLORS).map(([key, val]) => {
          const active = activeFilters.has(key);
          return (
            <Chip
              key={key}
              label={val.label}
              size="small"
              onClick={() => toggleFilter(key)}
              sx={{
                bgcolor: active ? val.chip : val.chip + '28',
                color:   active ? '#fff'   : val.chip,
                border:  `1px solid ${val.chip}${active ? '' : '50'}`,
                fontSize: '0.72rem',
                height: 20,
                cursor: 'pointer',
                fontWeight: active ? 700 : 400,
                '&:hover': { bgcolor: val.chip + '60' },
              }}
            />
          );
        })}
        {activeFilters.size > 0 && (
          <Chip
            label="Clear filters"
            size="small"
            onClick={() => setActiveFilters(new Set())}
            sx={{ bgcolor: '#37474f', color: '#b0bec5', fontSize: '0.72rem', height: 20, cursor: 'pointer' }}
          />
        )}
      </Box>

      {/* ── Search box ── */}
      <TextField
        size="small"
        placeholder="Search calculations, premiums, strikes\u2026"
        value={searchText}
        onChange={e => setSearchText(e.target.value)}
        sx={{ mb: 1.5, width: '100%' }}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon fontSize="small" sx={{ color: '#546e7a' }} />
            </InputAdornment>
          ),
          endAdornment: searchText ? (
            <InputAdornment position="end">
              <IconButton size="small" onClick={() => setSearchText('')}>
                <ClearIcon fontSize="small" />
              </IconButton>
            </InputAdornment>
          ) : null,
          sx: { fontFamily: 'monospace', fontSize: '0.8rem' },
        }}
      />

      {/* ── Walkthrough entry cards ── */}
      <Box
        ref={scrollRef}
        sx={{
          maxHeight: 'calc(100vh - 460px)',
          overflowY: 'auto',
          overflowX: 'hidden',
          pr: 0.5,
          '&::-webkit-scrollbar':       { width: 6 },
          '&::-webkit-scrollbar-thumb': { bgcolor: '#546e7a', borderRadius: 3 },
        }}
      >
        {loading ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <CircularProgress size={32} />
            <Typography variant="caption" display="block" color="text.secondary" mt={1}>
              Loading walkthrough\u2026
            </Typography>
          </Box>
        ) : visibleEntries.length === 0 ? (
          <Paper sx={{ p: 3, textAlign: 'center', bgcolor: '#263238', border: '1px dashed #546e7a' }}>
            <Typography color="text.secondary">
              {walkthrough.length === 0
                ? 'No walkthrough entries yet.'
                : 'No entries match current filters / search.'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {walkthrough.length === 0
                ? 'Entries appear after the first heartbeat runs.'
                : `${walkthrough.length} total \u2014 ${walkthrough.length - visibleEntries.length} filtered out.`}
            </Typography>
          </Paper>
        ) : (
          visibleEntries.map((entry, idx) => (
            <WalkthroughEntry
              key={entry.heartbeat != null ? entry.heartbeat : idx}
              entry={entry}
              index={idx === visibleEntries.length - 1 ? 0 : idx + 1}
            />
          ))
        )}
        <div ref={bottomRef} />
      </Box>
    </Box>
  );
}
