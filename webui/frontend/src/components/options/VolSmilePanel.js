/**
 * VolSmilePanel  (Feature 8)
 * ============================
 * Collapsible panel showing IV vs Strike (vol smile) per expiry.
 * Pure frontend — reads from positions array already in state.
 * Tabs per expiry: Mar 13 | Mar 20 | Mar 27
 * Put Skew metric (approx 25-delta put - call).
 *
 * Props:
 *   positions  — array from useOptionsPositions
 *   spotPrice  — current BTC spot
 */

import React, { useState, useMemo, useEffect } from 'react';
import {
  Box, Paper, Typography, IconButton, Chip, Tabs, Tab, Tooltip,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import BarChartIcon from '@mui/icons-material/BarChart';
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartTooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { alpha } from '@mui/material/styles';

const ACCENT = '#818cf8';
const NUMERIC_FONT = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace';
const CARD_MIN_HEIGHT = 318;
const CHART_HEIGHT = 180;
const FOOTER_MIN_HEIGHT = 34;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseExpiryFromSymbol(symbol) {
  try {
    const parts = symbol.split('-');
    if (parts.length < 4) return null;
    const raw = parts[3]; // "270326" = DDMMYY (27-Mar-2026)
    const dd = parseInt(raw.slice(0, 2), 10);
    const mm = parseInt(raw.slice(2, 4), 10);
    const yy = parseInt(raw.slice(4, 6), 10);
    return `20${String(yy).padStart(2, '0')}-${String(mm).padStart(2, '0')}-${String(dd).padStart(2, '0')}`;
  } catch (_) { return null; }
}

function computeDTE(expiryStr) {
  try {
    const exp = new Date(expiryStr);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return Math.max(0, Math.round((exp - today) / 86400000));
  } catch (_) { return 0; }
}

function groupByExpiry(positions) {
  const groups = {};
  for (const pos of positions) {
    if (!pos.product_symbol || !pos.iv) continue;
    const expiry = parseExpiryFromSymbol(pos.product_symbol);
    if (!expiry) continue;
    if (!groups[expiry]) groups[expiry] = [];
    groups[expiry].push(pos);
  }
  return groups;
}

/**
 * Approximate put skew: IV difference at equidistant OTM call/put strikes.
 * Finds put nearest 25% below spot and call nearest 25% above spot.
 */
function computePutSkew(positions, spotPrice) {
  if (!spotPrice) return null;
  const otmCalls = positions
    .filter(p => p.product_symbol.startsWith('C-') && p.iv)
    .map(p => {
      const strike = parseFloat(p.product_symbol.split('-')[2]);
      return { strike, iv: p.iv > 5 ? p.iv : p.iv * 100 };
    })
    .filter(p => p.strike > spotPrice)
    .sort((a, b) => Math.abs(a.strike - spotPrice * 1.25) - Math.abs(b.strike - spotPrice * 1.25));

  const otmPuts = positions
    .filter(p => p.product_symbol.startsWith('P-') && p.iv)
    .map(p => {
      const strike = parseFloat(p.product_symbol.split('-')[2]);
      return { strike, iv: p.iv > 5 ? p.iv : p.iv * 100 };
    })
    .filter(p => p.strike < spotPrice)
    .sort((a, b) => Math.abs(a.strike - spotPrice * 0.75) - Math.abs(b.strike - spotPrice * 0.75));

  if (!otmCalls.length || !otmPuts.length) return null;
  return +(otmPuts[0].iv - otmCalls[0].iv).toFixed(2);
}

function buildSmileData(positions, _spotPrice) {
  const calls = [];
  const puts = [];

  for (const pos of positions) {
    if (!pos.product_symbol || !pos.iv) continue;
    const strike = parseFloat(pos.product_symbol.split('-')[2]);
    if (!strike || isNaN(strike)) continue;
    const iv = pos.iv > 5 ? +pos.iv.toFixed(2) : +(pos.iv * 100).toFixed(2);
    if (pos.product_symbol.startsWith('C-')) calls.push({ strike, callIV: iv });
    else puts.push({ strike, putIV: iv });
  }

  // Merge calls + puts by strike
  const strikeMap = {};
  for (const c of calls) {
    strikeMap[c.strike] = { strike: c.strike, callIV: c.callIV };
  }
  for (const p of puts) {
    if (strikeMap[p.strike]) strikeMap[p.strike].putIV = p.putIV;
    else strikeMap[p.strike] = { strike: p.strike, putIV: p.putIV };
  }

  return Object.values(strikeMap).sort((a, b) => a.strike - b.strike);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const CustomCallDot = ({ cx, cy }) => (
  <circle cx={cx} cy={cy} r={5} fill="#3b82f6" stroke="#1e293b" strokeWidth={1} />
);
const CustomPutDot = ({ cx, cy }) => (
  <circle cx={cx} cy={cy} r={5} fill="#ef4444" stroke="#1e293b" strokeWidth={1} />
);

export default function VolSmilePanel({ positions, spotPrice }) {
  const [collapsed, setCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState(0);

  const expiryGroups = useMemo(() => groupByExpiry(positions || []), [positions]);
  const expiries = useMemo(
    () => Object.keys(expiryGroups).sort(),
    [expiryGroups]
  );

  const defaultTabIndex = useMemo(() => {
    if (expiries.length === 0) return 0;
    let maxIdx = 0;
    let maxCount = 0;
    expiries.forEach((exp, idx) => {
      const count = (expiryGroups[exp] || []).length;
      if (count > maxCount) {
        maxCount = count;
        maxIdx = idx;
      }
    });
    return maxIdx;
  }, [expiries, expiryGroups]);

  // Default to expiry with the most positions
  useEffect(() => {
    if (expiries.length > 0) {
      setActiveTab(defaultTabIndex);
    }
  }, [expiries.length, defaultTabIndex]);

  const activeExpiry = expiries[activeTab] || expiries[0];
  const activePositions = useMemo(
    () => expiryGroups[activeExpiry] || [],
    [expiryGroups, activeExpiry]
  );

  const smileData = useMemo(
    () => buildSmileData(activePositions, spotPrice),
    [activePositions, spotPrice]
  );

  const putSkew = useMemo(
    () => computePutSkew(activePositions, spotPrice),
    [activePositions, spotPrice]
  );

  const dte = activeExpiry ? computeDTE(activeExpiry) : 0;

  if (!positions?.length) return null;

  const headerContent = (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 0.7, minHeight: 30 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8, flexWrap: 'wrap', rowGap: 0.45 }}>
        <BarChartIcon sx={{ fontSize: '1rem', color: alpha(ACCENT, 0.92) }} />
        <Typography
          variant="subtitle2"
          sx={{
            color: '#e2e8f0',
            fontWeight: 800,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            fontSize: '0.74rem',
            lineHeight: 1,
          }}
        >
          Vol Smile
        </Typography>
        {putSkew !== null && (
          <Tooltip title="Put Skew: IV(25-delta Put) - IV(25-delta Call). High skew indicates expensive put protection.">
            <Chip
              label={`Put Skew: ${putSkew > 0 ? '+' : ''}${putSkew} pts${putSkew > 5 ? ' ⚠' : ''}`}
              size="small"
              sx={{
                bgcolor: putSkew > 5 ? alpha('#ef4444', 0.18) : alpha('#64748b', 0.3),
                color: putSkew > 5 ? '#f87171' : alpha('#cbd5e1', 0.9),
                border: `1px solid ${putSkew > 5 ? alpha('#ef4444', 0.45) : alpha('#64748b', 0.45)}`,
                fontSize: '0.63rem',
                height: 21,
                fontWeight: 800,
                '& .MuiChip-label': { px: 0.85, fontFamily: NUMERIC_FONT },
              }}
            />
          </Tooltip>
        )}
      </Box>
      <IconButton size="small" onClick={() => setCollapsed(c => !c)} sx={{ color: '#94a3b8', p: 0.45 }}>
        {collapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
      </IconButton>
    </Box>
  );

  return (
    <Paper
      sx={{
        p: 1.25,
        bgcolor: alpha('#0b1220', 0.92),
        border: `1px solid ${alpha(ACCENT, 0.28)}`,
        borderRadius: 2.2,
        mb: 1,
        height: '100%',
        minHeight: CARD_MIN_HEIGHT,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        backgroundImage: `
          radial-gradient(circle at 96% 0%, ${alpha(ACCENT, 0.12)} 0%, transparent 34%),
          linear-gradient(180deg, ${alpha('#0f172a', 0.82)} 0%, ${alpha('#0b1220', 0.94)} 100%)
        `,
        boxShadow: `0 12px 26px ${alpha('#000', 0.45)}`,
      }}
    >
      {headerContent}
      {!collapsed && (
        <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 0.8, flex: 1 }}>
          {expiries.length > 1 && (
            <Tabs
              value={Math.min(activeTab, expiries.length - 1)}
              onChange={(_, v) => setActiveTab(v)}
              sx={{
                minHeight: 29,
                mb: 0.7,
                '& .MuiTabs-flexContainer': { gap: 0.35 },
                '& .MuiTab-root': {
                  minHeight: 29,
                  minWidth: 82,
                  py: 0.35,
                  px: 0.9,
                  fontSize: '0.65rem',
                  color: alpha('#94a3b8', 0.82),
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  borderRadius: 999,
                },
                '& .Mui-selected': {
                  color: '#e2e8f0',
                  bgcolor: alpha(ACCENT, 0.2),
                  boxShadow: `0 0 0 1px ${alpha(ACCENT, 0.35)}`,
                },
                '& .MuiTabs-indicator': { display: 'none' },
              }}
            >
              {expiries.map((exp, i) => (
                <Tab key={exp} label={`${exp.slice(5).replace('-', '/')} (${computeDTE(exp)}d)`} value={i} />
              ))}
            </Tabs>
          )}

          {smileData.length < 2 ? (
            <Typography variant="caption" sx={{ color: alpha('#94a3b8', 0.8), fontSize: '0.7rem' }}>
              Need at least 2 positions in this expiry to plot smile.
            </Typography>
          ) : (
            <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
              <ComposedChart data={smileData} margin={{ top: 10, right: 20, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis
                  dataKey="strike"
                  tick={{ fill: '#94a3b8', fontSize: 10 }}
                  axisLine={{ stroke: '#334155' }}
                  tickLine={false}
                  tickFormatter={v => `$${(v / 1000).toFixed(0)}K`}
                />
                <YAxis
                  domain={['auto', 'auto']}
                  tick={{ fill: '#94a3b8', fontSize: 10 }}
                  axisLine={{ stroke: '#334155' }}
                  tickLine={false}
                  tickFormatter={v => `${v}%`}
                  width={42}
                />
                <RechartTooltip
                  contentStyle={{
                    background: 'rgba(10, 15, 28, 0.96)',
                    border: `1px solid ${alpha(ACCENT, 0.35)}`,
                    borderRadius: 8,
                    boxShadow: '0 10px 30px rgba(0,0,0,0.45)',
                  }}
                  labelStyle={{ color: '#e2e8f0', fontWeight: 700, letterSpacing: '0.03em' }}
                  itemStyle={{ color: '#e2e8f0', fontWeight: 700, fontSize: 12, fontFamily: NUMERIC_FONT }}
                  labelFormatter={v => `Strike: $${v.toLocaleString()}`}
                  formatter={(val, name) => val ? [`${val.toFixed(2)}%`, name] : ['-', name]}
                />
                {spotPrice && (
                  <ReferenceLine
                    x={spotPrice}
                    stroke="rgba(255,255,255,0.25)"
                    strokeDasharray="4 3"
                    label={{ value: 'Spot', fill: '#64748b', fontSize: 10, position: 'top' }}
                  />
                )}
                <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8', paddingTop: 6 }} />
                {smileData.some(d => d.callIV) && (
                  <Line
                    dataKey="callIV" name="Call IV"
                    stroke="#3b82f6" strokeWidth={1.5}
                    dot={<CustomCallDot />} connectNulls
                  />
                )}
                {smileData.some(d => d.putIV) && (
                  <Line
                    dataKey="putIV" name="Put IV"
                    stroke="#ef4444" strokeWidth={1.5}
                    dot={<CustomPutDot />} connectNulls
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          )}

          <Typography
            variant="caption"
            sx={{
              color: alpha('#94a3b8', 0.8),
              display: 'flex',
              alignItems: 'center',
              mt: 'auto',
              pt: 0.55,
              minHeight: FOOTER_MIN_HEIGHT,
              borderTop: `1px dashed ${alpha('#475569', 0.45)}`,
              fontSize: '0.65rem',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            Expiry {activeExpiry} ({dte}d) — {activePositions.length} positions used. Live IV updates.
          </Typography>
        </Box>
      )}
    </Paper>
  );
}
