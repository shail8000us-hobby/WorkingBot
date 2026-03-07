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
  const [collapsed, setCollapsed] = useState(true);
  const [activeTab, setActiveTab] = useState(0);

  const expiryGroups = useMemo(() => groupByExpiry(positions || []), [positions]);
  const expiries = useMemo(
    () => Object.keys(expiryGroups).sort(),
    [expiryGroups]
  );

  // Default to expiry with the most positions
  useEffect(() => {
    if (expiries.length > 0) {
      let maxIdx = 0;
      let maxCount = 0;
      expiries.forEach((exp, idx) => {
        const count = (expiryGroups[exp] || []).length;
        if (count > maxCount) { maxCount = count; maxIdx = idx; }
      });
      setActiveTab(maxIdx);
    }
  }, [expiries.length]); // only re-run when expiry count changes

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
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <BarChartIcon sx={{ fontSize: '1rem', color: '#94a3b8' }} />
        <Typography variant="subtitle2" sx={{ color: '#e2e8f0', fontWeight: 600 }}>
          Vol Smile
        </Typography>
        {putSkew !== null && (
          <Tooltip title="Put Skew: IV(25-delta Put) - IV(25-delta Call). High skew indicates expensive put protection.">
            <Chip
              label={`Put Skew: ${putSkew > 0 ? '+' : ''}${putSkew} pts${putSkew > 5 ? ' ⚠' : ''}`}
              size="small"
              sx={{
                bgcolor: putSkew > 5 ? 'rgba(239,68,68,0.2)' : 'rgba(71,85,105,0.3)',
                color: putSkew > 5 ? '#ef4444' : '#94a3b8',
                fontSize: '0.65rem',
                height: 18,
              }}
            />
          </Tooltip>
        )}
      </Box>
      <IconButton size="small" onClick={() => setCollapsed(c => !c)} sx={{ color: '#94a3b8' }}>
        {collapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
      </IconButton>
    </Box>
  );

  return (
    <Paper sx={{ p: 1.5, bgcolor: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(71, 85, 105, 0.3)', mb: 1 }}>
      {headerContent}
      {!collapsed && (
        <Box sx={{ mt: 1 }}>
          {expiries.length > 1 && (
            <Tabs
              value={Math.min(activeTab, expiries.length - 1)}
              onChange={(_, v) => setActiveTab(v)}
              sx={{
                minHeight: 28,
                mb: 1,
                '& .MuiTab-root': { minHeight: 28, py: 0.3, fontSize: '0.7rem', color: '#64748b' },
                '& .Mui-selected': { color: '#e2e8f0' },
                '& .MuiTabs-indicator': { bgcolor: '#3b82f6', height: 2 },
              }}
            >
              {expiries.map((exp, i) => (
                <Tab key={exp} label={`${exp.slice(5).replace('-', '/')} (${computeDTE(exp)}d)`} value={i} />
              ))}
            </Tabs>
          )}

          {smileData.length < 2 ? (
            <Typography variant="caption" sx={{ color: '#64748b' }}>
              Need at least 2 positions in this expiry to plot smile.
            </Typography>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
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
                  width={38}
                />
                <RechartTooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 6 }}
                  labelStyle={{ color: '#e2e8f0' }}
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
                <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
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

          <Typography variant="caption" sx={{ color: '#475569', display: 'block', mt: 0.5 }}>
            {activeExpiry} ({dte}d) — {activePositions.length} positions used. Updates live with IV feed.
          </Typography>
        </Box>
      )}
    </Paper>
  );
}
