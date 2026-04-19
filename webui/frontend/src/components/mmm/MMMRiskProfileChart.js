/**
 * MMMRiskProfileChart — Portfolio P&L Landscape Chart
 *
 * Fetches the P&L curve on-demand from /api/mmm/session/:id/pnl-curve
 * and renders a full chart showing: P&L curve, breakeven boundaries,
 * gamma boundary markers, current spot position, and option strikes.
 *
 * Props:
 *   sessionId: string — required
 *   isActive: bool — whether to show the chart (triggers initial fetch)
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  IconButton,
  Chip,
  Tooltip,
  Alert,
} from '@mui/material';
import { Refresh as RefreshIcon } from '@mui/icons-material';
import {
  ComposedChart,
  Area,
  ReferenceLine,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as ChartTooltip,
  ResponsiveContainer,
} from 'recharts';
import api from '../../utils/apiShim';

// Format a number as a BTC price
function fmtPrice(val) {
  if (val == null) return 'N/A';
  const k = Math.round(val / 1000);
  return `$${k}k`;
}

function fmtPriceFull(val) {
  if (val == null) return 'N/A';
  return '$' + Math.round(val).toLocaleString();
}

function fmtPnl(val) {
  if (val == null) return 'N/A';
  const sign = val >= 0 ? '+' : '';
  return `${sign}$${val.toFixed(2)}`;
}

// Custom tooltip for the chart
function CustomChartTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  const pnl = payload[0]?.value;
  const color = pnl >= 0 ? '#4caf50' : '#f44336';
  return (
    <Box sx={{
      backgroundColor: 'rgba(18,18,18,0.95)',
      border: `1px solid ${color}`,
      borderRadius: 1,
      p: 1,
      fontSize: '0.72rem',
    }}>
      <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
        Spot: {fmtPriceFull(label)}
      </Typography>
      <Typography variant="caption" sx={{ color, fontWeight: 700, fontFamily: 'monospace' }}>
        P&L: {fmtPnl(pnl)}
      </Typography>
    </Box>
  );
}

export default function MMMRiskProfileChart({ sessionId, isActive, breakeven: breakevenProp, onCurveLoaded }) {
  const [curveData, setCurveData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchCurve = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get(`/api/mmm/session/${sessionId}/pnl-curve`, { params: { n_points: 150 }, skipCircuit: true });
      if (data.success) {
        // Compute zero-crossings client-side if backend didn't provide them
        // This works without a backend restart as long as curve_points are present
        let enriched = data;
        if (!data.computed_breakeven && data.curve_points?.length >= 2) {
          const pts = data.curve_points;
          const crossings = [];
          for (let i = 0; i < pts.length - 1; i++) {
            const p0 = pts[i], p1 = pts[i + 1];
            if (p0.pnl * p1.pnl <= 0 && (p0.pnl !== 0 || p1.pnl !== 0)) {
              const d = p1.pnl - p0.pnl;
              const cross = d !== 0
                ? p0.spot - p0.pnl * (p1.spot - p0.spot) / d
                : (p0.spot + p1.spot) / 2;
              crossings.push(Math.round(cross * 100) / 100);
            }
          }
          if (crossings.length >= 2) {
            enriched = { ...data, computed_breakeven: {
              lower_breakeven: Math.min(...crossings),
              upper_breakeven: Math.max(...crossings),
              source: 'curve_zero_crossing',
            }};
          } else if (crossings.length === 1) {
            const zc = crossings[0];
            enriched = { ...data, computed_breakeven: zc < data.spot_price
              ? { lower_breakeven: zc, upper_breakeven: null, source: 'curve_zero_crossing' }
              : { lower_breakeven: null, upper_breakeven: zc, source: 'curve_zero_crossing' },
            };
          }
        }
        // Also attach pnl_at_spot from curve if backend didn't compute it
        if (enriched.pnl_at_spot == null && enriched.curve_points?.length) {
          const nearest = enriched.curve_points.reduce((best, p) =>
            Math.abs(p.spot - enriched.spot_price) < Math.abs(best.spot - enriched.spot_price) ? p : best
          );
          enriched = { ...enriched, pnl_at_spot: nearest.pnl };
        }
        setCurveData(enriched);
        if (onCurveLoaded) onCurveLoaded(enriched);
      } else {
        setError(data.error || 'Failed to load P&L curve');
      }
    } catch (err) {
      setError('Network error — is the backend running?');
    } finally {
      setLoading(false);
    }
  }, [sessionId, onCurveLoaded]);

  // Fetch when activated for the first time
  useEffect(() => {
    if (isActive && sessionId && !curveData && !loading) {
      fetchCurve();
    }
  }, [isActive, sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh when breakeven recomputes (positions changed — non-cache result)
  // breakevenProp.from_cache=false means a structural position change triggered a recompute
  const beComputedAt = breakevenProp?.computed_at;
  const beFromCache  = breakevenProp?.from_cache;
  useEffect(() => {
    if (isActive && sessionId && beComputedAt && beFromCache === false) {
      fetchCurve();
    }
  }, [beComputedAt, beFromCache]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!isActive) return null;

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 6 }}>
        <CircularProgress size={32} />
        <Typography variant="caption" sx={{ ml: 1.5, color: 'text.secondary' }}>
          Computing P&L landscape…
        </Typography>
      </Box>
    );
  }

  if (error) {
    const isNoSpot = error.includes('spot price');
    return (
      <Alert severity={isNoSpot ? 'warning' : 'error'} sx={{ m: 1 }} action={
        <IconButton size="small" onClick={fetchCurve}><RefreshIcon fontSize="small" /></IconButton>
      }>
        {isNoSpot
          ? 'Waiting for first heartbeat — P&L curve will appear once the session runs one cycle.'
          : error}
      </Alert>
    );
  }

  if (!curveData || !curveData.curve_points?.length) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <Typography variant="body2" color="text.secondary">
          No positions — P&L curve unavailable.
        </Typography>
        <IconButton size="small" onClick={fetchCurve} sx={{ mt: 1 }}>
          <RefreshIcon />
        </IconButton>
      </Box>
    );
  }

  const {
    curve_points,
    strike_markers = [],
    breakeven: beFromEngine,
    computed_breakeven: beFromCurve,
    pnl_at_spot: pnlAtSpotFromCurve,
    gamma,
    spot_price,
    scan_range_pct,
    positions_count,
    computed_at,
  } = curveData;

  // Use engine breakeven when available, fall back to zero-crossing computed from curve
  const breakeven = beFromEngine || beFromCurve || null;

  // Compute min/max P&L for gradient stop position
  const pnlValues = curve_points.map(p => p.pnl);
  const maxPnl = Math.max(...pnlValues, 0);
  const minPnl = Math.min(...pnlValues, 0);
  const range = maxPnl - minPnl;
  // Fraction from top (maxPnl) to zero — used for gradient stop
  const zeroFraction = range > 0 ? (maxPnl / range) : 0.5;
  const zeroStopPct = Math.max(0, Math.min(100, zeroFraction * 100)).toFixed(1);

  // Unique strikes for markers (deduplicate)
  const strikeSet = new Map();
  for (const sm of strike_markers) {
    const key = `${sm.strike}-${sm.side}`;
    if (!strikeSet.has(key)) strikeSet.set(key, sm);
  }

  // Format computed_at for display
  const computedLabel = computed_at
    ? new Date(computed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : null;

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1, px: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.primary' }}>
            📈 P&L Landscape
          </Typography>
          <Chip
            label={`${positions_count} positions`}
            size="small"
            sx={{ fontSize: '0.65rem', opacity: 0.7 }}
          />
          <Chip
            label={`±${scan_range_pct}%`}
            size="small"
            sx={{ fontSize: '0.65rem', opacity: 0.7 }}
          />
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {computedLabel && (
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
              {computedLabel}
            </Typography>
          )}
          <Tooltip title="Refresh P&L curve">
            <IconButton size="small" onClick={fetchCurve} disabled={loading}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Legend */}
      <Box sx={{ display: 'flex', gap: 1.5, mb: 1, px: 0.5, flexWrap: 'wrap' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Box sx={{ width: 12, height: 3, backgroundColor: '#ffffff', borderRadius: 1 }} />
          <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>Spot</Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Box sx={{ width: 12, height: 2, backgroundColor: '#ff7043', borderRadius: 1, borderStyle: 'dashed' }} />
          <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>Breakeven</Typography>
        </Box>
        {(gamma?.lower_gamma_boundary != null || gamma?.upper_gamma_boundary != null) && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 12, height: 2, backgroundColor: '#ab47bc', borderRadius: 1, borderStyle: 'dashed' }} />
            <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>Gamma</Typography>
          </Box>
        )}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Box sx={{ width: 12, height: 2, backgroundColor: 'rgba(120,120,120,0.6)', borderRadius: 1 }} />
          <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>Strikes</Typography>
        </Box>
      </Box>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={curve_points} margin={{ top: 4, right: 16, left: 4, bottom: 4 }}>
          <defs>
            <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4caf50" stopOpacity={0.35} />
              <stop offset={`${zeroStopPct}%`} stopColor="#4caf50" stopOpacity={0.08} />
              <stop offset={`${zeroStopPct}%`} stopColor="#f44336" stopOpacity={0.08} />
              <stop offset="100%" stopColor="#f44336" stopOpacity={0.35} />
            </linearGradient>
            <linearGradient id="pnlStrokeGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4caf50" stopOpacity={1} />
              <stop offset={`${zeroStopPct}%`} stopColor="#4caf50" stopOpacity={1} />
              <stop offset={`${zeroStopPct}%`} stopColor="#f44336" stopOpacity={1} />
              <stop offset="100%" stopColor="#f44336" stopOpacity={1} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />

          <XAxis
            dataKey="spot"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v) => fmtPrice(v)}
            tick={{ fontSize: 10, fill: '#777' }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
            scale="linear"
          />
          <YAxis
            tickFormatter={(v) => `$${v.toFixed(1)}`}
            tick={{ fontSize: 10, fill: '#777' }}
            tickLine={false}
            axisLine={false}
            width={52}
          />

          <ChartTooltip content={<CustomChartTooltip />} />

          {/* P&L curve */}
          <Area
            type="monotone"
            dataKey="pnl"
            stroke="url(#pnlStrokeGradient)"
            strokeWidth={2}
            fill="url(#pnlGradient)"
            dot={false}
            activeDot={{ r: 4, fill: '#fff', strokeWidth: 2 }}
            isAnimationActive={false}
          />

          {/* Zero line */}
          <ReferenceLine
            y={0}
            stroke="rgba(255,255,255,0.25)"
            strokeDasharray="4 4"
            strokeWidth={1}
          />

          {/* Current spot */}
          {spot_price > 0 && (
            <ReferenceLine
              x={spot_price}
              stroke="#ffffff"
              strokeWidth={2}
              label={{
                value: fmtPrice(spot_price),
                position: 'top',
                fontSize: 10,
                fill: '#ffffff',
                fontWeight: 700,
              }}
            />
          )}

          {/* Lower breakeven */}
          {breakeven?.lower_breakeven && (
            <ReferenceLine
              x={breakeven.lower_breakeven}
              stroke="#ff7043"
              strokeWidth={1.5}
              strokeDasharray="5 3"
              label={{
                value: fmtPrice(breakeven.lower_breakeven),
                position: 'insideBottomLeft',
                fontSize: 9,
                fill: '#ff7043',
              }}
            />
          )}

          {/* Upper breakeven */}
          {breakeven?.upper_breakeven && (
            <ReferenceLine
              x={breakeven.upper_breakeven}
              stroke="#ff7043"
              strokeWidth={1.5}
              strokeDasharray="5 3"
              label={{
                value: fmtPrice(breakeven.upper_breakeven),
                position: 'insideBottomRight',
                fontSize: 9,
                fill: '#ff7043',
              }}
            />
          )}

          {/* Gamma boundaries */}
          {gamma?.lower_gamma_boundary != null && (
            <ReferenceLine
              x={gamma.lower_gamma_boundary}
              stroke="#ab47bc"
              strokeWidth={1}
              strokeDasharray="3 4"
              label={{ value: 'γ↓', position: 'top', fontSize: 9, fill: '#ab47bc' }}
            />
          )}
          {gamma?.upper_gamma_boundary != null && (
            <ReferenceLine
              x={gamma.upper_gamma_boundary}
              stroke="#ab47bc"
              strokeWidth={1}
              strokeDasharray="3 4"
              label={{ value: 'γ↑', position: 'top', fontSize: 9, fill: '#ab47bc' }}
            />
          )}

          {/* Strike markers */}
          {Array.from(strikeSet.values()).map((sm) => (
            <ReferenceLine
              key={`strike-${sm.strike}-${sm.side}`}
              x={sm.strike}
              stroke={sm.side === 'CE' ? 'rgba(100,181,246,0.35)' : 'rgba(240,98,146,0.35)'}
              strokeWidth={1}
              strokeDasharray="2 4"
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Bottom info row */}
      <Box sx={{ display: 'flex', gap: 1, mt: 0.5, px: 0.5, flexWrap: 'wrap' }}>
        {breakeven?.zone && breakeven.zone !== 'SAFE' && (
          <Chip
            label={`BE Zone: ${breakeven.zone}`}
            size="small"
            sx={{
              fontSize: '0.65rem',
              color: breakeven.zone === 'CRITICAL' ? '#d32f2f' : breakeven.zone === 'DANGER' ? '#f44336' : '#ff9800',
              border: `1px solid currentColor`,
              backgroundColor: 'transparent',
            }}
          />
        )}
        {gamma?.gamma_zone && gamma.gamma_zone !== 'SAFE' && (
          <Chip
            label={`γ Zone: ${gamma.gamma_zone}`}
            size="small"
            sx={{
              fontSize: '0.65rem',
              color: '#ab47bc',
              border: '1px solid #ab47bc',
              backgroundColor: 'transparent',
            }}
          />
        )}
        {(() => {
          const pnlVal = breakeven?.pnl_at_spot ?? pnlAtSpotFromCurve;
          if (pnlVal == null) return null;
          return (
            <Chip
              label={`P&L: ${fmtPnl(pnlVal)}`}
              size="small"
              sx={{
                fontSize: '0.65rem',
                color: pnlVal >= 0 ? '#4caf50' : '#f44336',
                border: '1px solid currentColor',
                backgroundColor: 'transparent',
              }}
            />
          );
        })()}
        {beFromCurve && !beFromEngine && (
          <Chip
            label="BE computed"
            size="small"
            sx={{ fontSize: '0.65rem', color: '#ff9800', border: '1px solid #ff9800', backgroundColor: 'transparent' }}
          />
        )}
        <Typography variant="caption" sx={{ ml: 'auto', fontSize: '0.6rem', color: 'text.disabled', alignSelf: 'center' }}>
          Intrinsic-only model — conservative estimate
        </Typography>
      </Box>
    </Box>
  );
}
