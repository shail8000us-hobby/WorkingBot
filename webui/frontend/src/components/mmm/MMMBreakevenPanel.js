/**
 * MMMBreakevenPanel — Breakeven Band Visualization
 *
 * Displays the portfolio breakeven band with a scaled bar (proportional to
 * actual price distances), distance labels, aggression multiplier, and optional
 * gamma boundary markers overlaid on the same bar.
 *
 * Data source: mmm_breakeven event from WebSocket (embedded in mmm_heartbeat
 * payload as `breakeven` key, or standalone `mmm_breakeven` event).
 *
 * Props:
 *   breakeven: BreakevenResult dict
 *   gamma:     (optional) GammaResult dict — overlays gamma markers on the bar
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
export default function MMMBreakevenPanel({ breakeven, gamma }) {
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
    dte_scale = 1.0,
    effective_warning_pct,
    effective_danger_pct,
    effective_critical_pct,
  } = breakeven;

  const zoneStyle = ZONE_COLORS[zone] || ZONE_COLORS.SAFE;

  // Build the visual band bar — scaled to actual price distances
  const hasLower = lower_breakeven != null;
  const hasUpper = upper_breakeven != null;
  const hasBoth = hasLower && hasUpper;

  // Chart range: show ±(max distance × 1.4) from spot so boundaries sit at ~70% from center
  const distLower = hasLower ? Math.abs(spot_price - lower_breakeven) : 0;
  const distUpper = hasUpper ? Math.abs(upper_breakeven - spot_price) : 0;
  const maxDist = Math.max(distLower, distUpper, spot_price * 0.01); // floor 1%
  const chartRange = maxDist * 1.4; // padded range each side
  const chartLo = spot_price - chartRange;
  const chartHi = spot_price + chartRange;

  // Convert a price to a [0, 100] bar position
  const toBarPct = (price) => {
    if (price == null) return null;
    const pct = (price - chartLo) / (chartHi - chartLo) * 100;
    return Math.max(1, Math.min(99, pct));
  };

  const spotBarPct = toBarPct(spot_price);
  const lowerBarPct = hasLower ? toBarPct(lower_breakeven) : null;
  const upperBarPct = hasUpper ? toBarPct(upper_breakeven) : null;

  // Gamma boundary positions (optional overlay)
  const gammaBarPcts = [];
  if (gamma?.enabled) {
    if (gamma.lower_gamma_boundary != null) {
      const pct = toBarPct(gamma.lower_gamma_boundary);
      if (pct !== null) gammaBarPcts.push({ pct, spot: gamma.lower_gamma_boundary, side: 'lower' });
    }
    if (gamma.upper_gamma_boundary != null) {
      const pct = toBarPct(gamma.upper_gamma_boundary);
      if (pct !== null) gammaBarPcts.push({ pct, spot: gamma.upper_gamma_boundary, side: 'upper' });
    }
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
          {dte_scale > 1.01 && (
            <Tooltip title={`DTE threshold scaling active — thresholds widened ×${fmt(dte_scale, 2)} based on time remaining to expiry`} placement="top">
              <Chip
                label={`DTE ${fmt(dte_scale, 2)}×`}
                size="small"
                sx={{ fontWeight: 700, fontSize: '0.65rem', color: '#29b6f6', border: '1px solid #0288d1', backgroundColor: 'transparent' }}
              />
            </Tooltip>
          )}
          <IconButton size="small" onClick={() => setExpanded(e => !e)} sx={{ p: 0.25 }}>
            {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
          </IconButton>
        </Box>
      </Box>

      {/* Visual band bar — scaled to actual price distances */}
      <Box sx={{ position: 'relative', height: 28, mb: 0.75 }}>
        {/* Background track */}
        <Box sx={{
          position: 'absolute', top: '40%', left: 0, right: 0,
          height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.08)',
          transform: 'translateY(-50%)',
        }} />
        {/* Profit zone (between the breakevens) */}
        {hasBoth && lowerBarPct != null && upperBarPct != null && (
          <Box sx={{
            position: 'absolute', top: '40%',
            left: `${lowerBarPct}%`,
            width: `${upperBarPct - lowerBarPct}%`,
            height: 6, borderRadius: 2,
            backgroundColor: `${zoneStyle.border}30`,
            border: `1px solid ${zoneStyle.border}55`,
            transform: 'translateY(-50%)',
          }} />
        )}
        {/* Lower breakeven marker */}
        {hasLower && lowerBarPct != null && (
          <Tooltip title={`Lower Breakeven: ${fmtPrice(lower_breakeven)}`} placement="top">
            <Box sx={{
              position: 'absolute', top: '40%',
              left: `${lowerBarPct}%`,
              width: 3, height: 16, borderRadius: 1.5,
              backgroundColor: '#ff5722',
              transform: 'translate(-50%, -50%)',
              cursor: 'help',
            }} />
          </Tooltip>
        )}
        {/* Upper breakeven marker */}
        {hasUpper && upperBarPct != null && (
          <Tooltip title={`Upper Breakeven: ${fmtPrice(upper_breakeven)}`} placement="top">
            <Box sx={{
              position: 'absolute', top: '40%',
              left: `${upperBarPct}%`,
              width: 3, height: 16, borderRadius: 1.5,
              backgroundColor: '#ff5722',
              transform: 'translate(-50%, -50%)',
              cursor: 'help',
            }} />
          </Tooltip>
        )}
        {/* Gamma boundary markers (purple triangles) */}
        {gammaBarPcts.map((gb, i) => (
          <Tooltip key={i} title={`γ Boundary (${gb.side || 'kink'}): ${fmtPrice(gb.spot)}`} placement="top">
            <Box sx={{
              position: 'absolute', top: '40%',
              left: `${gb.pct}%`,
              width: 0, height: 0,
              borderLeft: '4px solid transparent',
              borderRight: '4px solid transparent',
              borderBottom: '7px solid #ab47bc',
              transform: 'translate(-50%, -100%)',
              cursor: 'help',
            }} />
          </Tooltip>
        ))}
        {/* Spot marker */}
        <Tooltip title={`Spot: ${fmtPrice(spot_price)}`} placement="top">
          <Box sx={{
            position: 'absolute', top: '40%',
            left: `${spotBarPct}%`,
            width: 12, height: 12, borderRadius: '50%',
            backgroundColor: '#ffffff',
            border: `2px solid ${zoneStyle.border}`,
            transform: 'translate(-50%, -50%)',
            cursor: 'help',
            zIndex: 2,
          }} />
        </Tooltip>
        {/* Labels below bar */}
        {hasLower && lowerBarPct != null && (
          <Typography variant="caption" sx={{
            position: 'absolute', top: '80%', left: `${lowerBarPct}%`,
            transform: 'translateX(-50%)',
            fontSize: '0.6rem', color: '#ff5722', whiteSpace: 'nowrap',
          }}>
            {fmtPrice(lower_breakeven)}
          </Typography>
        )}
        {hasUpper && upperBarPct != null && (
          <Typography variant="caption" sx={{
            position: 'absolute', top: '80%', left: `${upperBarPct}%`,
            transform: 'translateX(-50%)',
            fontSize: '0.6rem', color: '#ff5722', whiteSpace: 'nowrap',
          }}>
            {fmtPrice(upper_breakeven)}
          </Typography>
        )}
        <Typography variant="caption" sx={{
          position: 'absolute', top: '80%',
          left: `${spotBarPct}%`,
          transform: 'translateX(-50%)',
          fontSize: '0.6rem', color: '#ffffff', fontWeight: 700, whiteSpace: 'nowrap',
        }}>
          {fmtPrice(spot_price)}
        </Typography>
      </Box>

      {/* Distance row */}
      <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between', gap: 1 }}>
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
            {dte_scale > 1.01 && effective_warning_pct != null && (
              <Grid item xs={12}>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.25 }}>
                  Effective Thresholds (DTE {fmt(dte_scale, 2)}×)
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.72rem' }}>
                  <span style={{ color: '#ff9800' }}>W {fmt(effective_warning_pct, 2)}%</span>
                  {' / '}
                  <span style={{ color: '#f44336' }}>D {fmt(effective_danger_pct, 2)}%</span>
                  {' / '}
                  <span style={{ color: '#d32f2f' }}>C {fmt(effective_critical_pct, 2)}%</span>
                </Typography>
              </Grid>
            )}
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
