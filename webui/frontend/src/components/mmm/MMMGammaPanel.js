/**
 * MMMGammaPanel — Gamma Detector Visualization
 *
 * Displays portfolio curvature boundaries — spots where loss rate begins to
 * accelerate. Companion to MMMBreakevenPanel.
 *
 * Data source: gamma key from mmm_heartbeat WebSocket event, or standalone
 * mmm_gamma event. Observation-only until gamma_severity_multiplier_enabled.
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

const ZONE_COLORS = {
  SAFE:    { bg: 'rgba(76,175,80,0.08)',   border: '#4caf50', text: '#4caf50', label: '🟢 SAFE'    },
  WARNING: { bg: 'rgba(255,152,0,0.10)',   border: '#ff9800', text: '#ff9800', label: '🟡 WARNING' },
  DANGER:  { bg: 'rgba(244,67,54,0.10)',   border: '#f44336', text: '#f44336', label: '🔴 DANGER'  },
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
 * MMMGammaPanel
 *
 * Props:
 *   gamma: GammaResult dict from session._gamma_result
 */
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
              fontWeight: 700,
              fontSize: '0.7rem',
              color: zoneStyle.text,
              border: `1px solid ${zoneStyle.border}`,
              backgroundColor: 'transparent',
            }}
          />
          {observation_only && (
            <Chip
              label="Observation Only"
              size="small"
              sx={{
                fontWeight: 600,
                fontSize: '0.65rem',
                color: '#9e9e9e',
                border: '1px solid #9e9e9e',
                backgroundColor: 'transparent',
              }}
            />
          )}
          <IconButton size="small" onClick={() => setExpanded(e => !e)} sx={{ p: 0.25 }}>
            {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
          </IconButton>
        </Box>
      </Box>

      {/* Nearest distance summary */}
      <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.72rem' }}>
        Nearest boundary: {nearest_distance_pct != null ? `${fmt(nearest_distance_pct)}% (${nearest_side})` : 'None detected'}
      </Typography>

      {/* Boundary distance row */}
      <Box sx={{ mt: 0.75, display: 'flex', justifyContent: 'space-between', gap: 1 }}>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
          ▼ Lower: {fmtDist(lower_distance_pct, spot_price)}
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
          ▲ Upper: {fmtDist(upper_distance_pct, spot_price)}
        </Typography>
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
              <Tooltip title="Negative = losses accelerate rapidly near this price. Normalized per unit BTC exposure." placement="top">
                <Typography variant="caption" color="text.secondary" display="block" sx={{ cursor: 'help', textDecoration: 'underline dotted' }}>
                  Severity Lower
                </Typography>
              </Tooltip>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', color: gamma_severity_lower != null && gamma_severity_lower < 0 ? '#f44336' : 'text.primary' }}>
                {gamma_severity_lower != null ? fmt(gamma_severity_lower, 3) : 'N/A'}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Tooltip title="Negative = losses accelerate rapidly near this price. Normalized per unit BTC exposure." placement="top">
                <Typography variant="caption" color="text.secondary" display="block" sx={{ cursor: 'help', textDecoration: 'underline dotted' }}>
                  Severity Upper
                </Typography>
              </Tooltip>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', color: gamma_severity_upper != null && gamma_severity_upper < 0 ? '#f44336' : 'text.primary' }}>
                {gamma_severity_upper != null ? fmt(gamma_severity_upper, 3) : 'N/A'}
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
                Gamma boundaries show where option strikes cause loss acceleration
              </Typography>
            </Grid>
          </Grid>
        </Box>
      </Collapse>
    </Box>
  );
}
