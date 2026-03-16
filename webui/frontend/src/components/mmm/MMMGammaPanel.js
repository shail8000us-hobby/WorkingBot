/**
 * MMMGammaPanel — Gamma Detector Visualization
 *
 * Displays portfolio curvature boundaries with:
 * - Zone chip (SAFE / WARNING / DANGER)
 * - Proximity meter: scaled bar showing spot relative to gamma boundaries
 * - Severity bars: visual magnitude for lower and upper boundary severity
 * - Expandable detail grid
 *
 * Data source: gamma key from mmm_heartbeat WebSocket event.
 *
 * Props:
 *   gamma: GammaResult dict from session._gamma_result
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

const ZONE_COLORS = {
  SAFE:    { bg: 'rgba(171,71,188,0.05)',  border: '#7b1fa2', text: '#ab47bc', label: '🟢 SAFE'    },
  WARNING: { bg: 'rgba(171,71,188,0.10)',  border: '#9c27b0', text: '#ce93d8', label: '🟡 WARNING' },
  DANGER:  { bg: 'rgba(171,71,188,0.18)',  border: '#ab47bc', text: '#f48fb1', label: '🔴 DANGER'  },
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
 * SeverityBar — shows a normalized severity value as a fill bar.
 * severity is negative (more negative = more severe), so we invert for display.
 */
function SeverityBar({ label, severity, zone }) {
  if (severity == null) {
    return (
      <Box sx={{ mb: 0.5 }}>
        <Typography variant="caption" sx={{ fontSize: '0.68rem', color: 'text.disabled' }}>
          {label}: No boundary detected
        </Typography>
      </Box>
    );
  }

  // Severity is negative — clamp to [0, 1] for bar display
  // Using -5 as "full bar" reference (very high severity)
  const mag = Math.abs(severity);
  const fillPct = Math.min(100, (mag / 5.0) * 100);
  const barColor = zone === 'DANGER' ? '#f44336' : zone === 'WARNING' ? '#ff9800' : '#ab47bc';

  return (
    <Box sx={{ mb: 0.75 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
        <Typography variant="caption" sx={{ fontSize: '0.68rem', color: 'text.secondary' }}>
          {label}
        </Typography>
        <Typography variant="caption" sx={{ fontSize: '0.68rem', fontFamily: 'monospace', color: barColor }}>
          {fmt(severity, 3)}
        </Typography>
      </Box>
      <Box sx={{
        width: '100%', height: 5, borderRadius: 2.5,
        backgroundColor: 'rgba(255,255,255,0.06)',
        overflow: 'hidden',
      }}>
        <Box sx={{
          width: `${fillPct}%`, height: '100%', borderRadius: 2.5,
          backgroundColor: barColor,
          opacity: 0.75,
          transition: 'width 0.3s ease',
        }} />
      </Box>
    </Box>
  );
}

export default function MMMGammaPanel({ gamma }) {
  const [expanded, setExpanded] = useState(false);

  if (!gamma || !gamma.enabled) return null;

  const {
    lower_gamma_boundary,
    upper_gamma_boundary,
    gamma_severity_lower,
    gamma_severity_upper,
    gamma_zone = 'SAFE',
    lower_distance_pct,
    upper_distance_pct,
    nearest_distance_pct,
    nearest_side,
    spot_price,
    from_cache = false,
    positions_included = 0,
    perp_included = false,
    observation_only = true,
  } = gamma;

  const zoneStyle = ZONE_COLORS[gamma_zone] || ZONE_COLORS.SAFE;
  const hasLower = lower_gamma_boundary != null;
  const hasUpper = upper_gamma_boundary != null;

  // Proximity meter: scaled bar (same logic as breakeven bar)
  const distLower = hasLower ? Math.abs(spot_price - lower_gamma_boundary) : 0;
  const distUpper = hasUpper ? Math.abs(upper_gamma_boundary - spot_price) : 0;
  const maxDist = Math.max(distLower, distUpper, spot_price * 0.01);
  const chartRange = maxDist * 1.4;
  const chartLo = spot_price - chartRange;
  const chartHi = spot_price + chartRange;

  const toBarPct = (price) => {
    if (price == null) return null;
    const pct = (price - chartLo) / (chartHi - chartLo) * 100;
    return Math.max(1, Math.min(99, pct));
  };

  const spotBarPct = toBarPct(spot_price);
  const lowerBarPct = hasLower ? toBarPct(lower_gamma_boundary) : null;
  const upperBarPct = hasUpper ? toBarPct(upper_gamma_boundary) : null;

  return (
    <Box sx={{
      p: 1.5,
      borderRadius: 1.5,
      border: `1px solid ${zoneStyle.border}`,
      backgroundColor: zoneStyle.bg,
      mb: 2,
    }}>
      {/* Header row */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.75 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.primary' }}>
          ⚡ Gamma Boundaries
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Chip
            label={zoneStyle.label}
            size="small"
            sx={{
              fontWeight: 700, fontSize: '0.7rem',
              color: zoneStyle.text,
              border: `1px solid ${zoneStyle.border}`,
              backgroundColor: 'transparent',
            }}
          />
          {observation_only && (
            <Chip
              label="Obs Only"
              size="small"
              sx={{
                fontWeight: 600, fontSize: '0.65rem',
                color: '#9e9e9e', border: '1px solid #9e9e9e',
                backgroundColor: 'transparent',
              }}
            />
          )}
          <IconButton size="small" onClick={() => setExpanded(e => !e)} sx={{ p: 0.25 }}>
            {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
          </IconButton>
        </Box>
      </Box>

      {/* Proximity meter */}
      {(hasLower || hasUpper) ? (
        <Box sx={{ position: 'relative', height: 28, mb: 0.5 }}>
          {/* Track */}
          <Box sx={{
            position: 'absolute', top: '40%', left: 0, right: 0,
            height: 5, borderRadius: 2.5, backgroundColor: 'rgba(255,255,255,0.07)',
            transform: 'translateY(-50%)',
          }} />
          {/* Zone between boundaries */}
          {hasLower && hasUpper && lowerBarPct != null && upperBarPct != null && (
            <Box sx={{
              position: 'absolute', top: '40%',
              left: `${lowerBarPct}%`,
              width: `${upperBarPct - lowerBarPct}%`,
              height: 5, borderRadius: 2,
              backgroundColor: `${zoneStyle.border}25`,
              border: `1px solid ${zoneStyle.border}40`,
              transform: 'translateY(-50%)',
            }} />
          )}
          {/* Lower boundary marker */}
          {hasLower && lowerBarPct != null && (
            <Tooltip title={`Lower γ Boundary: ${fmtPrice(lower_gamma_boundary)}`} placement="top">
              <Box sx={{
                position: 'absolute', top: '40%',
                left: `${lowerBarPct}%`,
                width: 2, height: 14, borderRadius: 1,
                backgroundColor: '#ab47bc',
                transform: 'translate(-50%, -50%)', cursor: 'help',
              }} />
            </Tooltip>
          )}
          {/* Upper boundary marker */}
          {hasUpper && upperBarPct != null && (
            <Tooltip title={`Upper γ Boundary: ${fmtPrice(upper_gamma_boundary)}`} placement="top">
              <Box sx={{
                position: 'absolute', top: '40%',
                left: `${upperBarPct}%`,
                width: 2, height: 14, borderRadius: 1,
                backgroundColor: '#ab47bc',
                transform: 'translate(-50%, -50%)', cursor: 'help',
              }} />
            </Tooltip>
          )}
          {/* Spot marker */}
          <Tooltip title={`Spot: ${fmtPrice(spot_price)}`} placement="top">
            <Box sx={{
              position: 'absolute', top: '40%',
              left: `${spotBarPct}%`,
              width: 10, height: 10, borderRadius: '50%',
              backgroundColor: '#ffffff',
              border: `2px solid ${zoneStyle.border}`,
              transform: 'translate(-50%, -50%)',
              cursor: 'help', zIndex: 2,
            }} />
          </Tooltip>
          {/* Labels */}
          {hasLower && lowerBarPct != null && (
            <Typography variant="caption" sx={{
              position: 'absolute', top: '80%', left: `${lowerBarPct}%`,
              transform: 'translateX(-50%)',
              fontSize: '0.6rem', color: '#ab47bc', whiteSpace: 'nowrap',
            }}>
              {fmtPrice(lower_gamma_boundary)}
            </Typography>
          )}
          {hasUpper && upperBarPct != null && (
            <Typography variant="caption" sx={{
              position: 'absolute', top: '80%', left: `${upperBarPct}%`,
              transform: 'translateX(-50%)',
              fontSize: '0.6rem', color: '#ab47bc', whiteSpace: 'nowrap',
            }}>
              {fmtPrice(upper_gamma_boundary)}
            </Typography>
          )}
        </Box>
      ) : (
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.72rem', display: 'block', mb: 0.5 }}>
          No gamma boundaries detected in scan range
        </Typography>
      )}

      {/* Distance row */}
      <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between', gap: 1 }}>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
          ▼ Lower: {fmtDist(lower_distance_pct, spot_price)}
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
          ▲ Upper: {fmtDist(upper_distance_pct, spot_price)}
        </Typography>
      </Box>

      {/* Severity bars */}
      <Box sx={{ mt: 1 }}>
        <SeverityBar label="Lower severity" severity={gamma_severity_lower} zone={gamma_zone} />
        <SeverityBar label="Upper severity" severity={gamma_severity_upper} zone={gamma_zone} />
      </Box>

      {/* Expanded details */}
      <Collapse in={expanded}>
        <Box sx={{ mt: 1.5, pt: 1.5, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
          <Grid container spacing={1}>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" display="block">Lower Boundary</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                {fmtPrice(lower_gamma_boundary)}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" display="block">Upper Boundary</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                {fmtPrice(upper_gamma_boundary)}
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
              <Typography variant="caption" color="text.secondary" display="block">Positions Scanned</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                {positions_included}{perp_included ? ' + perp' : ''}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary" display="block">Spot Price</Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                {fmtPrice(spot_price)}
              </Typography>
            </Grid>
            {from_cache && (
              <Grid item xs={12}>
                <Typography variant="caption" color="text.secondary">
                  Cached — recomputes on next position change
                </Typography>
              </Grid>
            )}
            <Grid item xs={12}>
              <Typography variant="caption" sx={{ color: '#9e9e9e', fontStyle: 'italic' }}>
                Gamma boundaries = option strikes where loss rate accelerates (P&L curve kinks)
              </Typography>
            </Grid>
          </Grid>
        </Box>
      </Collapse>
    </Box>
  );
}
