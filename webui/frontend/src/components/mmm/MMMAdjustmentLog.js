/**
 * MMMAdjustmentLog — Money Mind & Method
 *
 * Timeline of all adjustment events including:
 * - Standard adjustments (green) — with loss/premium context
 * - Reversals (orange) — with direction + P&L detail
 * - First-reversal (amber with P&L detail)
 * - Skipped/cooldown (gray)
 * - Strike shifts (blue with before/after)
 * - Close-at-5 events (green with "PROFIT LOCKED" badge)
 * - Both-sides decisions (red/amber with user choice)
 *
 * Maps to MONEY_POWER_CALCULATION_LOGIC.md §5, §6, §8, §9, §10, §11
 *
 * Created: February 15, 2026
 * Updated: February 16, 2026 — Fixed timestamps (UTC), added informative tooltips,
 *          enriched adjustment descriptions with why/context
 */

import React, { useMemo } from 'react';
import {
  Box,
  Typography,
  Chip,
  Paper,
  Divider,
  Tooltip,
} from '@mui/material';
import {
  TrendingUp as AdjIcon,
  SwapHoriz as ReversalIcon,
  Lock as LockIcon,
  MoveUp as ShiftIcon,
  WarningAmber as BothSidesIcon,
} from '@mui/icons-material';

const TYPE_CONFIG = {
  standard: { color: '#4caf50', bg: 'rgba(76,175,80,0.08)', label: 'Standard', icon: AdjIcon },
  reversal: { color: '#ff9800', bg: 'rgba(255,152,0,0.08)', label: 'Reversal', icon: ReversalIcon },
  first_reversal: { color: '#ffc107', bg: 'rgba(255,193,7,0.08)', label: '1st Reversal', icon: ReversalIcon },
  cooldown: { color: '#9e9e9e', bg: 'rgba(158,158,158,0.08)', label: 'Cooldown', icon: null },
  shift: { color: '#2196f3', bg: 'rgba(33,150,243,0.08)', label: 'Strike Shift', icon: ShiftIcon },
  close_at_5: { color: '#00c853', bg: 'rgba(0,200,83,0.08)', label: 'Profit Locked', icon: LockIcon },
  both_sides_decision: { color: '#f44336', bg: 'rgba(244,67,54,0.06)', label: 'Both Sides', icon: BothSidesIcon },
};

/**
 * Parse timestamp as UTC — backend stores UTC ISO strings without 'Z' suffix.
 * Adding 'Z' ensures the browser doesn't misinterpret as local time.
 */
function parseUTC(timestamp) {
  if (!timestamp) return null;
  const ts = timestamp.endsWith('Z') ? timestamp : timestamp + 'Z';
  return new Date(ts);
}

function formatTime(timestamp) {
  if (!timestamp) return '--';
  try {
    const d = parseUTC(timestamp);
    if (!d || isNaN(d.getTime())) return '--';
    return d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    });
  } catch {
    return '--';
  }
}

/**
 * Human-readable label for adjustment type
 */
function adjTypeLabel(type) {
  switch (type) {
    case 'standard': return 'Trend continuation — aggressor kept rising';
    case 'reversal': return 'Market reversed — now hedging the opposite direction';
    case 'first_reversal': return 'First reversal — hedging only naked adjustment P&L';
    default: return type || 'Standard';
  }
}

/**
 * Build an informative description explaining WHY this adjustment happened
 */
function buildDescription(entry) {
  const side = entry.side || '??';
  const lots = entry.lots_sold || entry.lots || 0;
  const premium = entry.premium || 0;
  const strike = entry.strike || 0;
  const aggressor = entry.aggressor || '';
  const type = entry.type || 'standard';

  // Main action line
  let action = `Sell ${lots} ${side} @ ${Number(strike).toLocaleString()} for ${Number(premium).toFixed(2)}`;

  // Why line — context about what triggered this
  let why = '';
  if (aggressor && aggressor !== side) {
    why = `${aggressor} side breached trigger → hedging with ${side}`;
  } else if (aggressor) {
    why = `${aggressor} premium exceeded trigger level`;
  }

  if (type === 'first_reversal') {
    why = `Market reversed → ${aggressor} adjustments underwater → hedging with ${side}`;
  } else if (type === 'reversal') {
    why = `Market reversed direction → ${aggressor} now aggressor → selling ${side}`;
  }

  return { action, why };
}

function AdjustmentEntry({ entry, number }) {
  const cfg = TYPE_CONFIG[entry.type || 'standard'] || TYPE_CONFIG.standard;
  const Icon = cfg.icon;

  const isBothSides = entry.type === 'both_sides_decision';

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 1.5,
        p: 1.5,
        borderRadius: 1,
        bgcolor: cfg.bg,
        border: '1px solid',
        borderColor: `${cfg.color}30`,
      }}
    >
      {/* Number */}
      <Typography
        variant="caption"
        sx={{
          fontWeight: 700,
          color: cfg.color,
          minWidth: 24,
          textAlign: 'center',
          pt: 0.25,
        }}
      >
        #{number}
      </Typography>

      {/* Icon */}
      {Icon && <Icon sx={{ fontSize: 18, color: cfg.color, mt: 0.25 }} />}

      {/* Content */}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, flexWrap: 'wrap' }}>
          <Tooltip
            title={adjTypeLabel(entry.type)}
            placement="top"
            arrow
          >
            <Chip
              label={cfg.label}
              size="small"
              sx={{
                bgcolor: `${cfg.color}20`,
                color: cfg.color,
                fontWeight: 600,
                fontSize: '0.78rem',
                height: 20,
                cursor: 'help',
              }}
            />
          </Tooltip>
          <Tooltip
            title={
              entry.timestamp
                ? parseUTC(entry.timestamp)?.toLocaleString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                  hour12: true,
                }) || ''
                : ''
            }
            placement="top"
          >
            <Typography variant="caption" color="text.secondary" sx={{ cursor: 'help' }}>
              {formatTime(entry.timestamp)}
            </Typography>
          </Tooltip>
        </Box>

        {/* Main description — varies by type */}
        {entry.type === 'shift' ? (
          <Box>
            <Typography variant="body2">
              {entry.side} shift: {Number(entry.old_strike || 0).toLocaleString()} →{' '}
              {Number(entry.new_strike || 0).toLocaleString()}
              {entry.frozen_lots > 0 && (
                <Typography component="span" variant="caption" color="text.secondary">
                  {' '}({entry.frozen_lots} lots frozen)
                </Typography>
              )}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
              Opposing premium too low for effective hedging — shifted to closer strike (§10)
            </Typography>
          </Box>
        ) : entry.type === 'close_at_5' ? (
          <Box>
            <Typography variant="body2">
              Closed {entry.lots} {entry.side} @ {Number(entry.strike || 0).toLocaleString()}
              <Typography component="span" variant="caption" sx={{ color: '#00c853', fontWeight: 600, ml: 1 }}>
                +${(entry.realized_pnl || 0).toFixed(2)} locked
              </Typography>
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
              Premium dropped to ≤5 — profit locked by buying back (§11)
            </Typography>
          </Box>
        ) : isBothSides ? (
          <Box>
            <Typography variant="body2" sx={{ color: '#f44336' }}>
              Both sides triggered — User chose: <strong>{entry.decision?.replace('_', ' ')}</strong>
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
              CE and PE both exceeded triggers simultaneously (§8)
            </Typography>
          </Box>
        ) : (
          <Box>
            {(() => {
              const { action, why } = buildDescription(entry);
              return (
                <>
                  <Typography variant="body2">{action}</Typography>
                  {why && (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
                      ↳ {why}
                    </Typography>
                  )}
                </>
              );
            })()}
          </Box>
        )}

        {/* Loss covered + premium collected */}
        {(entry.loss_covered > 0 || entry.premium_collected > 0) && (
          <Box sx={{ mt: 0.5, display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
            {entry.loss_covered > 0 && (
              <Typography variant="caption" sx={{ color: '#ef5350' }}>
                Loss: ${Number(entry.loss_covered).toFixed(2)}
              </Typography>
            )}
            {entry.premium_collected > 0 && (
              <Typography variant="caption" sx={{ color: '#4caf50' }}>
                Collected: ${Number(entry.premium_collected).toFixed(2)}
              </Typography>
            )}
            {entry.premium_collected > 0 && entry.loss_covered > 0 && (
              <Typography variant="caption" sx={{
                color: entry.premium_collected >= entry.loss_covered ? '#4caf50' : '#ff9800',
                fontWeight: 600,
              }}>
                {entry.premium_collected >= entry.loss_covered
                  ? `✓ Covered (+$${(entry.premium_collected - entry.loss_covered).toFixed(2)} buffer)`
                  : `⚠ Short by $${(entry.loss_covered - entry.premium_collected).toFixed(2)}`
                }
              </Typography>
            )}
          </Box>
        )}

        {/* Reversal P&L detail */}
        {entry.adjustment_pnl != null && entry.type?.includes('reversal') && (
          <Typography variant="caption" sx={{ color: entry.adjustment_pnl >= 0 ? '#4caf50' : '#f44336', display: 'block', mt: 0.25 }}>
            Adjustment P&L: {entry.adjustment_pnl >= 0 ? '+' : ''}${Number(entry.adjustment_pnl).toFixed(2)}
            {entry.adjustment_pnl >= 0
              ? ' (adjustments still profitable)'
              : ' (adjustments underwater → hedging)'}
          </Typography>
        )}
      </Box>
    </Box>
  );
}

export default function MMMAdjustmentLog({
  adjustments = [],
  reversals = [],
  shifts = [],
  closeEvents = [],
  session,
}) {
  // Merge all events into a single chronological timeline
  const timeline = useMemo(() => {
    const events = [];

    // From session history (most reliable)
    const history = session?.adjustment_history || [];
    history.forEach((h, i) => {
      events.push({
        ...h,
        _source: 'history',
        _number: h.adjustment_number || i + 1,
        _ts: parseUTC(h.timestamp)?.getTime() || 0,
      });
    });

    // Add WebSocket-sourced events not in history
    shifts.forEach((s) => {
      events.push({
        ...s,
        type: 'shift',
        _source: 'ws',
        _number: null,
        _ts: parseUTC(s.timestamp)?.getTime() || 0,
      });
    });

    closeEvents.forEach((c) => {
      events.push({
        ...c,
        type: 'close_at_5',
        _source: 'ws',
        _number: null,
        _ts: parseUTC(c.timestamp)?.getTime() || 0,
      });
    });

    // Deduplicate and sort (newest first)
    const unique = [];
    const seen = new Set();
    events
      .sort((a, b) => b._ts - a._ts)
      .forEach((e) => {
        const key = `${e.type}-${e._ts}-${e.side}`;
        if (!seen.has(key)) {
          seen.add(key);
          unique.push(e);
        }
      });

    return unique;
  }, [session, shifts, closeEvents]);

  if (timeline.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary" sx={{ mb: 1 }}>
          No adjustments yet.
        </Typography>
        <Typography variant="caption" color="text.secondary">
          The engine checks every heartbeat interval. If a side's premium exceeds its trigger,
          it will sell the opposite side to hedge the new loss. Each action will appear here
          with full context.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      {/* Summary bar */}
      <Box sx={{
        display: 'flex', gap: 1, flexWrap: 'wrap', mb: 0.5,
        px: 1, py: 0.5, borderRadius: 1,
        bgcolor: 'rgba(255,255,255,0.02)',
      }}>
        {(() => {
          const counts = {};
          timeline.forEach(e => {
            const t = e.type || 'standard';
            counts[t] = (counts[t] || 0) + 1;
          });
          return Object.entries(counts).map(([type, count]) => {
            const cfg = TYPE_CONFIG[type] || TYPE_CONFIG.standard;
            return (
              <Chip
                key={type}
                label={`${cfg.label}: ${count}`}
                size="small"
                sx={{
                  height: 18,
                  fontSize: '0.78rem',
                  bgcolor: `${cfg.color}15`,
                  color: cfg.color,
                }}
              />
            );
          });
        })()}
      </Box>

      {timeline.map((entry, idx) => (
        <AdjustmentEntry
          key={`${entry._source}-${idx}`}
          entry={entry}
          number={entry._number || timeline.length - idx}
        />
      ))}
    </Box>
  );
}
