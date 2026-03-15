/**
 * MMMBreakevenPanel — Breakeven Band Visualization
 *
 * Displays the portfolio breakeven band, distance to breakeven boundaries,
 * current risk zone, aggression multiplier, and diagnostic warnings.
 *
 * Data source: mmm_breakeven event from WebSocket (embedded in mmm_heartbeat
 * payload as `breakeven` key, or standalone `mmm_breakeven` event).
 *
 * Created: March 15, 2026
 */

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Chip,
  Collapse,
  IconButton,
  Grid,
  Tooltip,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';

// Zone color mapping
const ZONE_COLORS = {
  SAFE:     { bg: 'rgba(76,175,80,0.08)',     border: '#4caf50', text: '#4caf50',  label: '🟢 SAFE'     },
  WARNING:  { bg: 'rgba(255,152,0,0.10)',      border: '#ff9800', text: '#ff9800',  label: '🟡 WARNING'  },
  DANGER:   { bg: 'rgba(244,67,54,0.10)',      border: '#f44336', text: '#f44336',  label: '🔴 DANGER'   },
  CRITICAL: { bg: 'rgba(211,47,47,0.18)',      border: '#d32f2f', text: '#d32f2f',  label: '🚨 CRITICAL' },
};

function fmt(val, decimals = 1) {
  if (val == null) return 'N/A';
  return typeof val === 'number' ? val.toFixed(decimals) : val;
}

function fmtPrice(val) {
  if (val == null) return 'N/A';
  return '$' + Math.round(val).toLocaleString();
}

function fmtDist(distPct, spot) {
  if (distPct == null || spot == null) return 'N/A';
  const dollars = Math.round(spot * distPct / 100);
  return `${fmt(distPct)}% ($${dollars.toLocaleString()})`;
}

/**
 * MMMBreakevenPanel
 *
 * Props:
 *   breakeven: BreakevenResult dict from session._breakeven_result
 *              (available in heartbeat.breakeven or session._breakeven_result)
 */
export default function MMMBreakevenPanel({ breakeven }) {
  const [expanded, setExpanded] = useState(false);

  if (!breakeven || !breakeven.enabled) return null;

  const {
    lower_breakeven,
    upper_breakeven,
    spot_price,
    distance_lower_pct,
    distance_upper_pct,
    nearest_distance_pct,
    nearest_side,
    zone = 'SAFE',
    multiplier = 1.0,
    pnl_at_spot,
    band_width_pct,
    band_contracting,
    is_narrow_band,
    positions_included = 0,
    perp_included = false,
    from_cache = false,
  } = breakeven;

  const zoneStyle = ZONE_COLORS[zone] || ZONE_COLORS.SAFE;

  // Build the visual band bar
  const hasLower = lower_breakeven != null;
  const hasUpper = upper_breakeven != null;
  const hasBoth = hasLower && hasUpper;

  // Position spot as percentage along the band bar
  let spotPct = 50; // default center
  if (hasBoth && lower_breakeven < upper_breakeven) {
    const total = upper_breakeven - lower_breakeven;
    const fromLower = spot_price - lower_breakeven;
    spotPct = Math.max(5, Math.min(95, (fromLower / total) * 100));
  }

  return (
    <Box sx={{
      p: 1.5,
      borderRadius: 1.5,
      border: `1px solid ${zoneStyle.border}`,
      backgroundColor: zoneStyle.bg,
      mb: 2,
    }}>
      {/* Header row */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.primary' }}>
          🎯 Breakeven Band
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Chip
            label={zoneStyle.label}
            size="small"
            sx={{
              fontWeight: 700,
              fontSize: '0.7rem',
              color: zoneStyle.text,
              border: `1px solid ${zoneStyle.border}`,
              backgroundColor: 'transparent',
            }}
          />
          {multiplier > 1.0 && (
            <Chip
              label={`${fmt(multiplier, 2)}x`}
              size="small"
              sx={{ fontWeight: 700, fontSize: '0.7rem', color: '#ff9800', border: '1px solid #ff9800', backgroundColor: 'transparent' }}
            />
          )}
          <IconButton size="small" onClick={() => setExpanded(e => !e)} sx={{ p: 0.25 }}>
            {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
          </IconButton>
        </Box>
      </Box>

      {/* Visual band bar */}
      <Box sx={{ position: 'relative', height: 24, mb: 0.75 }}>
        {/* Background track */}
        <Box sx={{
          position: 'absolute', top: '50%', left: 0, right: 0,
          height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.08)',
          transform: 'translateY(-50%)',
        }} />
        {/* Colored zone band (between the breakevens) */}
        {hasBoth && (
          <Box sx={{
            position: 'absolute', top: '50%',
            left: '10%', right: '10%',
            height: 6, borderRadius: 3,
            backgroundColor: `${zoneStyle.border}33`,
            transform: 'translateY(-50%)',
          }} />
        )}
        {/* Lower breakeven marker */}
        {hasLower && (
          <Tooltip title={`Lower Breakeven: ${fmtPrice(lower_breakeven)}`} placement="top">
            <Box sx={{
              position: 'absolute', top: '50%',
              left: hasUpper ? `${10}%` : '30%',
              width: 3, height: 16, borderRadius: 1.5,
              backgroundColor: '#ff5722',
              transform: 'translate(-50%, -50%)',
              cursor: 'help',
            }} />
          </Tooltip>
        )}
        {/* Upper breakeven marker */}
        {hasUpper && (
          <Tooltip title={`Upper Breakeven: ${fmtPrice(upper_breakeven)}`} placement="top">
            <Box sx={{
              position: 'absolute', top: '50%',
              left: hasLower ? `${90}%` : '70%',
              width: 3, height: 16, borderRadius: 1.5,
              backgroundColor: '#ff5722',
              transform: 'translate(-50%, -50%)',
              cursor: 'help',
            }} />
          </Tooltip>
        )}
        {/* Spot marker */}
        <Tooltip title={`Spot: ${fmtPrice(spot_price)}`} placement="top">
          <Box sx={{
            position: 'absolute', top: '50%',
            left: hasBoth ? `${10 + spotPct * 0.8}%` : '50%',
            width: 10, height: 10, borderRadius: '50%',
            backgroundColor: '#ffffff',
            border: `2px solid ${zoneStyle.border}`,
            transform: 'translate(-50%, -50%)',
            cursor: 'help',
            zIndex: 2,
          }} />
        </Tooltip>
        {/* Labels below bar */}
        {hasLower && (
          <Typography variant="caption" sx={{
            position: 'absolute', top: '100%', left: hasBoth ? '10%' : '30%',
            transform: 'translateX(-50%)',
            fontSize: '0.6rem', color: 'text.secondary', whiteSpace: 'nowrap',
          }}>
            {fmtPrice(lower_breakeven)}
          </Typography>
        )}
        {hasUpper && (
          <Typography variant="caption" sx={{
            position: 'absolute', top: '100%', left: hasBoth ? '90%' : '70%',
            transform: 'translateX(-50%)',
            fontSize: '0.6rem', color: 'text.secondary', whiteSpace: 'nowrap',
          }}>
            {fmtPrice(upper_breakeven)}
          </Typography>
        )}
        <Typography variant="caption" sx={{
          position: 'absolute', top: '100%',
          left: hasBoth ? `${10 + spotPct * 0.8}%` : '50%',
          transform: 'translateX(-50%)',
          fontSize: '0.6rem', color: '#ffffff', fontWeight: 700, whiteSpace: 'nowrap',
        }}>
          {fmtPrice(spot_price)}
        </Typography>
      </Box>

      {/* Distance row — with extra top margin to clear labels */}
      <Box sx={{ mt: 2.5, display: 'flex', justifyContent: 'space-between', gap: 1 }}>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
          ▼ Lower: {fmtDist(distance_lower_pct, spot_price)}
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
          ▲ Upper: {fmtDist(distance_upper_pct, spot_price)}
        </Typography>
      </Box>

      {/* Warning chips */}
      {(band_contracting || is_narrow_band) && (
        <Box sx={{ mt: 0.75, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {band_contracting && (
            <Chip
              label={`🟠 Band contracting (${fmt(breakeven.band_width_prev_pct)}% → ${fmt(band_width_pct)}%)`}
              size="small"
              sx={{ fontSize: '0.65rem', color: '#ff9800', border: '1px solid #ff9800', backgroundColor: 'transparent' }}
            />
          )}
          {is_narrow_band && (
            <Chip
              label={`⚠️ Narrow Band (${fmt(band_width_pct)}%) — Consider reducing exposure`}
              size="small"
              sx={{ fontSize: '0.65rem', color: '#ffcc02', border: '1px solid #ffcc02', backgroundColor: 'transparent' }}
            />
          )}
        </Box>
      )}

      {/* Expanded details */}
      <Collapse in={expanded}>
        <Box sx={{ mt: 1.5, pt: 1.5, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
          <Grid container spacing={1}>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" display="block">Lower Breakeven</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                {fmtPrice(lower_breakeven)}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" display="block">Upper Breakeven</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                {fmtPrice(upper_breakeven)}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" display="block">Nearest Side</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', textTransform: 'uppercase' }}>
                {nearest_side}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" display="block">Nearest Distance</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', color: zoneStyle.text, fontWeight: 700 }}>
                {fmtDist(nearest_distance_pct, spot_price)}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" display="block">Band Width</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                {band_width_pct != null ? `${fmt(band_width_pct)}%` : 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" display="block">Aggression</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', color: multiplier > 1 ? '#ff9800' : '#4caf50', fontWeight: 700 }}>
                {fmt(multiplier, 2)}x
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" display="block">P&L at Spot</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', color: pnl_at_spot >= 0 ? '#4caf50' : '#f44336' }}>
                {pnl_at_spot != null ? `$${pnl_at_spot.toFixed(2)}` : 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" display="block">Positions</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                {positions_included}{perp_included ? ' + perp' : ''}
              </Typography>
            </Grid>
            {from_cache && (
              <Grid item xs={12}>
                <Typography variant="caption" color="text.secondary">
                  Cached — recomputes on next position change
                </Typography>
              </Grid>
            )}
          </Grid>
        </Box>
      </Collapse>
    </Box>
  );
}
