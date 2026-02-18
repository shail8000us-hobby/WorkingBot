/**
 * MMMStrikeMap — Money Mind & Method
 *
 * Visual map of all strikes with positions:
 * - Active strikes: bright circle with lot count
 * - Frozen strikes: dimmed circle with lot count, "(frozen)" label
 * - Closed strikes: crossed out with realized profit shown
 * - BTC spot price shown as horizontal divider
 * - Strike shift shown as arrow from old to new
 *
 * Maps to MONEY_POWER_CALCULATION_LOGIC.md §10 (Strike Shifting)
 *
 * Created: February 15, 2026
 */

import React, { useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  Tooltip,
  Divider,
} from '@mui/material';
import { HELP } from './MMMEducation';

function collectStrikes(session) {
  const entries = [];
  if (!session) return entries;

  for (const sideKey of ['ce', 'pe']) {
    const side = session[sideKey];
    if (!side) continue;

    const activeStrike = side.active_strike || 0;

    // Active strike
    if (activeStrike > 0 && side.active_lots > 0) {
      entries.push({
        strike: activeStrike,
        side: sideKey,
        type: 'active',
        lots: side.active_lots,
        label: `${sideKey.toUpperCase()} active (${side.active_lots}L)`,
      });
    }

    // Frozen positions
    const frozenByStrike = {};
    (side.frozen_positions || []).forEach((f) => {
      const s = f.strike || 0;
      if (s > 0) {
        if (!frozenByStrike[s]) frozenByStrike[s] = 0;
        frozenByStrike[s] += f.lots || 0;
      }
    });

    Object.entries(frozenByStrike).forEach(([strike, lots]) => {
      entries.push({
        strike: Number(strike),
        side: sideKey,
        type: 'frozen',
        lots,
        label: `${sideKey.toUpperCase()} frozen (${lots}L)`,
      });
    });
  }

  // Sort by strike value (descending — higher strikes on top)
  entries.sort((a, b) => b.strike - a.strike);
  return entries;
}

function StrikeEntry({ entry, spotPrice }) {
  const isActive = entry.type === 'active';
  const isCE = entry.side === 'ce';
  const sideColor = isCE ? '#2196f3' : '#9c27b0';
  const aboveSpot = entry.strike > spotPrice;

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        py: 0.75,
        px: 1.5,
        opacity: isActive ? 1 : 0.55,
        borderLeft: `3px solid ${isActive ? sideColor : '#9e9e9e'}`,
        bgcolor: isActive ? `${sideColor}08` : 'transparent',
        borderRadius: '0 4px 4px 0',
      }}
    >
      {/* Indicator dot */}
      <Box
        sx={{
          width: 10,
          height: 10,
          borderRadius: '50%',
          bgcolor: isActive ? sideColor : '#9e9e9e',
          flexShrink: 0,
        }}
      />

      {/* Strike value */}
      <Typography
        variant="body2"
        sx={{
          fontFamily: 'monospace',
          fontWeight: isActive ? 700 : 400,
          minWidth: 80,
          textDecoration: entry.type === 'closed' ? 'line-through' : 'none',
        }}
      >
        {Number(entry.strike).toLocaleString()}
      </Typography>

      {/* Side + type */}
      <Chip
        label={entry.label}
        size="small"
        variant={isActive ? 'filled' : 'outlined'}
        sx={{
          fontSize: '0.85rem',
          height: 20,
          fontWeight: 600,
          bgcolor: isActive ? `${sideColor}15` : 'transparent',
          color: isActive ? sideColor : '#9e9e9e',
          borderColor: isActive ? sideColor : '#9e9e9e',
        }}
      />

      {/* Current marker + explanation */}
      {isActive && (
        <Tooltip title={isCE ? 'Active CE strike — the algo monitors this strike\'s premium and uses it for CE-side adjustment calculations.' : 'Active PE strike — the algo monitors this strike\'s premium and uses it for PE-side adjustment calculations.'} arrow>
          <Typography variant="caption" sx={{ color: sideColor, fontWeight: 600, cursor: 'help' }}>
            ← current
          </Typography>
        </Tooltip>
      )}
      {!isActive && (
        <Tooltip title="Frozen — this strike has positions from before a strike shift. Still tracked for Close-at-5 profit locking, but not used in new adjustments." arrow>
          <Typography variant="caption" sx={{ color: '#9e9e9e', fontStyle: 'italic', cursor: 'help' }}>
            frozen
          </Typography>
        </Tooltip>
      )}
    </Box>
  );
}

export default function MMMStrikeMap({ session, spotPrice = 0 }) {
  const entries = useMemo(() => collectStrikes(session), [session]);

  if (entries.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, textAlign: 'center' }}>
        <Typography color="text.secondary" variant="body2">
          No positions yet. Once the session starts, you'll see all strikes with positions here — active strikes that the algo is using and frozen strikes from previous shifts.
        </Typography>
      </Paper>
    );
  }

  // Find where to insert BTC spot divider
  const spotInsertIdx = entries.findIndex((e) => e.strike <= spotPrice);

  return (
    <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
      <Box sx={{ px: 2, py: 1, bgcolor: 'action.hover' }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Strike Map
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontStyle: 'italic', fontSize: '0.85rem' }}>
          Visual layout of positions across strikes. CE strikes (calls) are above BTC spot, PE (puts) are below. Active = currently monitored. Frozen = old positions after a strike shift.
        </Typography>
      </Box>
      <Box sx={{ py: 1 }}>
        {entries.map((entry, idx) => (
          <React.Fragment key={`${entry.side}-${entry.strike}-${entry.type}`}>
            {/* Insert BTC spot divider */}
            {idx === spotInsertIdx && spotPrice > 0 && (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  px: 1.5,
                  py: 0.5,
                  my: 0.5,
                }}
              >
                <Divider sx={{ flex: 1 }} />
                <Chip
                  label={`BTC: ${Number(spotPrice).toLocaleString()}`}
                  size="small"
                  color="primary"
                  sx={{ fontWeight: 600, fontSize: '0.78rem' }}
                />
                <Divider sx={{ flex: 1 }} />
              </Box>
            )}
            <StrikeEntry entry={entry} spotPrice={spotPrice} />
          </React.Fragment>
        ))}

        {/* If spot is below all strikes, show at bottom */}
        {spotInsertIdx === -1 && spotPrice > 0 && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1.5, py: 0.5, mt: 0.5 }}>
            <Divider sx={{ flex: 1 }} />
            <Chip
              label={`BTC: ${Number(spotPrice).toLocaleString()}`}
              size="small"
              color="primary"
              sx={{ fontWeight: 600, fontSize: '0.78rem' }}
            />
            <Divider sx={{ flex: 1 }} />
          </Box>
        )}
      </Box>
    </Paper>
  );
}
