/**
 * MMMCombinedZoneWidget — Linear Concentric Zone Bar
 *
 * Visualizes the "concentric ring" mental model on a 1D horizontal bar:
 * - Inner gamma boundaries (purple) are CLOSER to spot — early warning
 * - Outer breakeven boundaries (orange) are FARTHER — loss threshold
 *
 * Shows both boundaries on a single shared scale so operators immediately
 * see how much buffer remains between spot and each boundary layer.
 *
 * Props:
 *   breakeven: BreakevenResult dict (from heartbeat.breakeven)
 *   gamma:     GammaResult dict (from heartbeat.gamma), optional
 */

import React from 'react';
import { Box, Typography, Chip, Tooltip } from '@mui/material';

function fmtPrice(val) {
  if (val == null) return 'N/A';
  return '$' + Math.round(val).toLocaleString();
}

function fmtPct(val) {
  if (val == null) return '—';
  return `${val.toFixed(1)}%`;
}

const ZONE_COLOR = {
  SAFE:     '#4caf50',
  WARNING:  '#ff9800',
  DANGER:   '#f44336',
  CRITICAL: '#d32f2f',
};

export default function MMMCombinedZoneWidget({ breakeven, gamma, computedBreakeven, spotPrice: spotPriceProp }) {
  const spot = breakeven?.spot_price || gamma?.spot_price || spotPriceProp;

  // No live data yet — show a waiting placeholder so the card is always visible
  const hasEngineData = breakeven?.enabled || gamma?.enabled;
  const hasComputedData = computedBreakeven && spot && spot > 0;
  if (!hasEngineData && !hasComputedData) {
    return (
      <Box sx={{
        p: 1.5,
        borderRadius: 1.5,
        border: '1px solid rgba(255,255,255,0.08)',
        backgroundColor: 'rgba(255,255,255,0.02)',
        mb: 2,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.primary' }}>
            🎚 Combined Zone View
          </Typography>
        </Box>
        <Typography variant="caption" color="text.secondary">
          Waiting for P&amp;L curve — open the Risk tab to load.
        </Typography>
      </Box>
    );
  }

  // Fall back to curve-computed breakeven when engine is disabled
  const effectiveBreakeven = (breakeven?.enabled && breakeven) || null;
  const computedBeLower = computedBreakeven?.lower_breakeven;
  const computedBeUpper = computedBreakeven?.upper_breakeven;

  // Collect all boundary prices for scale computation
  const beLower = effectiveBreakeven?.lower_breakeven ?? computedBeLower;
  const beUpper = effectiveBreakeven?.upper_breakeven ?? computedBeUpper;
  const gLower  = gamma?.lower_gamma_boundary;
  const gUpper  = gamma?.upper_gamma_boundary;

  // Compute chart range: 40% beyond the furthest boundary from spot
  const distances = [beLower, beUpper, gLower, gUpper]
    .filter(v => v != null)
    .map(v => Math.abs(v - spot));
  const maxDist = distances.length > 0
    ? Math.max(...distances) * 1.5
    : spot * 0.15;

  const chartLo = spot - maxDist;
  const chartHi = spot + maxDist;

  const toBarPct = (price) => {
    if (price == null) return null;
    const pct = (price - chartLo) / (chartHi - chartLo) * 100;
    return Math.max(0.5, Math.min(99.5, pct));
  };

  const spotPct = toBarPct(spot);

  // Compute zone color from breakeven (primary) or gamma (secondary)
  const overallZone = breakeven?.zone || gamma?.gamma_zone || 'SAFE';
  const overallColor = ZONE_COLOR[overallZone] || ZONE_COLOR.SAFE;

  return (
    <Box sx={{
      p: 1.5,
      borderRadius: 1.5,
      border: '1px solid rgba(255,255,255,0.12)',
      backgroundColor: 'rgba(255,255,255,0.03)',
      mb: 2,
    }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.primary' }}>
          🎚 Combined Zone View
        </Typography>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          {gamma?.enabled && (
            <Chip
              label="γ Inner"
              size="small"
              sx={{ fontSize: '0.65rem', color: '#ab47bc', border: '1px solid #ab47bc', backgroundColor: 'transparent' }}
            />
          )}
          {(breakeven?.enabled || computedBreakeven) && (
            <Chip
              label={breakeven?.enabled ? 'BE Outer' : 'BE Computed'}
              size="small"
              sx={{ fontSize: '0.65rem', color: '#ff7043', border: '1px solid #ff7043', backgroundColor: 'transparent' }}
            />
          )}
          {breakeven?.dte_scale > 1.01 && (
            <Tooltip title={`DTE threshold scaling active — thresholds widened ×${breakeven.dte_scale.toFixed(2)} based on time remaining to expiry`} placement="top">
              <Chip
                label={`DTE ${breakeven.dte_scale.toFixed(2)}×`}
                size="small"
                sx={{ fontSize: '0.65rem', color: '#29b6f6', border: '1px solid #0288d1', backgroundColor: 'transparent' }}
              />
            </Tooltip>
          )}
        </Box>
      </Box>

      {/* The zone bar */}
      <Box sx={{ position: 'relative', height: 36, mb: 0.5 }}>
        {/* Base track */}
        <Box sx={{
          position: 'absolute', top: '42%', left: 0, right: 0,
          height: 8, borderRadius: 4,
          backgroundColor: 'rgba(255,255,255,0.06)',
          transform: 'translateY(-50%)',
        }} />

        {/* Breakeven safe zone (between BE boundaries) — outermost colored band */}
        {beLower != null && beUpper != null && (
          <Box sx={{
            position: 'absolute', top: '42%',
            left: `${toBarPct(beLower)}%`,
            width: `${toBarPct(beUpper) - toBarPct(beLower)}%`,
            height: 8, borderRadius: 3,
            backgroundColor: 'rgba(255,112,67,0.15)',
            border: '1px solid rgba(255,112,67,0.3)',
            transform: 'translateY(-50%)',
          }} />
        )}

        {/* Gamma safe zone (between gamma boundaries) — inner band, slightly taller */}
        {gLower != null && gUpper != null && (
          <Box sx={{
            position: 'absolute', top: '42%',
            left: `${toBarPct(gLower)}%`,
            width: `${toBarPct(gUpper) - toBarPct(gLower)}%`,
            height: 12, borderRadius: 4,
            backgroundColor: 'rgba(171,71,188,0.15)',
            border: '1px solid rgba(171,71,188,0.35)',
            transform: 'translateY(-50%)',
          }} />
        )}

        {/* Breakeven boundary markers */}
        {beLower != null && (
          <Tooltip title={`Lower Breakeven: ${fmtPrice(beLower)}`} placement="top">
            <Box sx={{
              position: 'absolute', top: '42%',
              left: `${toBarPct(beLower)}%`,
              width: 3, height: 20, borderRadius: 1.5,
              backgroundColor: '#ff7043',
              transform: 'translate(-50%, -50%)', cursor: 'help',
            }} />
          </Tooltip>
        )}
        {beUpper != null && (
          <Tooltip title={`Upper Breakeven: ${fmtPrice(beUpper)}`} placement="top">
            <Box sx={{
              position: 'absolute', top: '42%',
              left: `${toBarPct(beUpper)}%`,
              width: 3, height: 20, borderRadius: 1.5,
              backgroundColor: '#ff7043',
              transform: 'translate(-50%, -50%)', cursor: 'help',
            }} />
          </Tooltip>
        )}

        {/* Gamma boundary markers — slightly shorter, purple */}
        {gLower != null && (
          <Tooltip title={`Lower γ Boundary: ${fmtPrice(gLower)}`} placement="top">
            <Box sx={{
              position: 'absolute', top: '42%',
              left: `${toBarPct(gLower)}%`,
              width: 2, height: 16, borderRadius: 1,
              backgroundColor: '#ab47bc',
              transform: 'translate(-50%, -50%)', cursor: 'help',
            }} />
          </Tooltip>
        )}
        {gUpper != null && (
          <Tooltip title={`Upper γ Boundary: ${fmtPrice(gUpper)}`} placement="top">
            <Box sx={{
              position: 'absolute', top: '42%',
              left: `${toBarPct(gUpper)}%`,
              width: 2, height: 16, borderRadius: 1,
              backgroundColor: '#ab47bc',
              transform: 'translate(-50%, -50%)', cursor: 'help',
            }} />
          </Tooltip>
        )}

        {/* Spot marker — center, bright white */}
        <Tooltip title={`Spot: ${fmtPrice(spot)}`} placement="top">
          <Box sx={{
            position: 'absolute', top: '42%',
            left: `${spotPct}%`,
            width: 12, height: 12, borderRadius: '50%',
            backgroundColor: '#ffffff',
            border: `2px solid ${overallColor}`,
            transform: 'translate(-50%, -50%)',
            cursor: 'help', zIndex: 3,
          }} />
        </Tooltip>

        {/* Price labels below bar */}
        {beLower != null && (
          <Typography variant="caption" sx={{
            position: 'absolute', top: '90%', left: `${toBarPct(beLower)}%`,
            transform: 'translateX(-50%)',
            fontSize: '0.58rem', color: '#ff7043', whiteSpace: 'nowrap',
          }}>
            {fmtPrice(beLower)}
          </Typography>
        )}
        {beUpper != null && (
          <Typography variant="caption" sx={{
            position: 'absolute', top: '90%', left: `${toBarPct(beUpper)}%`,
            transform: 'translateX(-50%)',
            fontSize: '0.58rem', color: '#ff7043', whiteSpace: 'nowrap',
          }}>
            {fmtPrice(beUpper)}
          </Typography>
        )}
      </Box>

      {/* Distance summary row */}
      <Box sx={{ mt: 2.5, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
        {breakeven?.enabled ? (
          <Box>
            <Typography variant="caption" sx={{ fontSize: '0.65rem', color: '#ff7043', fontWeight: 600 }}>
              BE nearest:
            </Typography>
            <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary', ml: 0.5 }}>
              {fmtPct(breakeven.nearest_distance_pct)} ({breakeven.nearest_side})
            </Typography>
          </Box>
        ) : computedBreakeven && spot > 0 ? (() => {
          const distances = [computedBeLower, computedBeUpper]
            .filter(v => v != null)
            .map(v => ({ pct: Math.abs(v - spot) / spot * 100, side: v < spot ? 'lower' : 'upper' }));
          const nearest = distances.length > 0 ? distances.reduce((a, b) => a.pct < b.pct ? a : b) : null;
          return nearest ? (
            <Box>
              <Typography variant="caption" sx={{ fontSize: '0.65rem', color: '#ff7043', fontWeight: 600 }}>
                BE nearest:
              </Typography>
              <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary', ml: 0.5 }}>
                {fmtPct(nearest.pct)} ({nearest.side}) ⟨curve⟩
              </Typography>
            </Box>
          ) : null;
        })() : null}
        {gamma?.enabled && (
          <Box>
            <Typography variant="caption" sx={{ fontSize: '0.65rem', color: '#ab47bc', fontWeight: 600 }}>
              γ nearest:
            </Typography>
            <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary', ml: 0.5 }}>
              {fmtPct(gamma.nearest_distance_pct)} ({gamma.nearest_side})
            </Typography>
          </Box>
        )}
        {breakeven?.multiplier > 1.0 && (
          <Box>
            <Typography variant="caption" sx={{ fontSize: '0.65rem', color: '#ff9800', fontWeight: 600 }}>
              BE mult:
            </Typography>
            <Typography variant="caption" sx={{ fontSize: '0.65rem', color: '#ff9800', ml: 0.5, fontFamily: 'monospace' }}>
              {breakeven.multiplier.toFixed(2)}x
            </Typography>
          </Box>
        )}
        {breakeven?.dte_scale > 1.01 && breakeven?.effective_warning_pct != null && (
          <Box>
            <Typography variant="caption" sx={{ fontSize: '0.65rem', color: '#29b6f6', fontWeight: 600 }}>
              Thresholds:
            </Typography>
            <Typography variant="caption" sx={{ fontSize: '0.65rem', ml: 0.5, fontFamily: 'monospace' }}>
              <span style={{ color: '#ff9800' }}>W {breakeven.effective_warning_pct.toFixed(2)}%</span>
              {' / '}
              <span style={{ color: '#f44336' }}>D {breakeven.effective_danger_pct.toFixed(2)}%</span>
              {' / '}
              <span style={{ color: '#d32f2f' }}>C {breakeven.effective_critical_pct.toFixed(2)}%</span>
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}
