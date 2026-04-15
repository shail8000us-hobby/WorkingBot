/**
 * VolTermStructurePanel  (Feature 7)
 * ====================================
 * Collapsible panel showing ATM IV per expiry as a line chart.
 * Pure frontend — reads from positions array already in state.
 * No new API calls. Uses Recharts (already installed).
 *
 * Props:
 *   positions  — array from useOptionsPositions
 *   spotPrice  — current BTC spot
 */

import React, { useState, useMemo } from 'react';
import {
  Box, Paper, Typography, IconButton, Chip,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartTooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { alpha } from '@mui/material/styles';

const ACCENT = '#38bdf8';
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
  } catch (_) {
    return null;
  }
}

function computeDTE(expiryStr) {
  try {
    const exp = new Date(expiryStr);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return Math.max(0, Math.round((exp - today) / 86400000));
  } catch (_) {
    return 0;
  }
}

function avg(arr) {
  if (!arr.length) return null;
  return arr.reduce((s, v) => s + v, 0) / arr.length;
}

function computeTermStructure(positions, spotPrice) {
  if (!positions?.length || !spotPrice) return [];

  // Group by expiry
  const byExpiry = {};
  for (const pos of positions) {
    if (!pos.product_symbol || !pos.iv) continue;
    const ivVal = pos.iv > 5 ? pos.iv / 100 : pos.iv; // normalise to decimal
    if (!ivVal || ivVal <= 0) continue;
    const expiry = parseExpiryFromSymbol(pos.product_symbol);
    if (!expiry) continue;
    const isCall = pos.product_symbol.startsWith('C-');
    const isPut = pos.product_symbol.startsWith('P-');

    if (!byExpiry[expiry]) byExpiry[expiry] = { calls: [], puts: [] };
    // ATM filter: within 5% of spot
    const strike = parseFloat(pos.product_symbol.split('-')[2]);
    const pctFromSpot = Math.abs(strike - spotPrice) / spotPrice;
    const isATM = pctFromSpot <= 0.05;

    if (isATM) {
      if (isCall) byExpiry[expiry].calls.push(ivVal * 100);  // store as %
      if (isPut)  byExpiry[expiry].puts.push(ivVal * 100);
    }
  }

  const result = Object.entries(byExpiry)
    .map(([expiry, { calls, puts }]) => {
      const allIVs = [...calls, ...puts];
      const atmIV = avg(allIVs);
      const callIV = avg(calls);
      const putIV = avg(puts);
      if (atmIV === null) return null;
      const dte = computeDTE(expiry);
      const label = expiry.slice(5).replace('-', '/'); // "03/13"
      return { expiry, label, dte, atmIV: +atmIV.toFixed(2), callIV: callIV ? +callIV.toFixed(2) : null, putIV: putIV ? +putIV.toFixed(2) : null };
    })
    .filter(Boolean)
    .sort((a, b) => a.dte - b.dte);

  return result;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const CustomDot = ({ cx, cy, payload, color }) => (
  <g>
    <circle cx={cx} cy={cy} r={5} fill={color} stroke="#1e293b" strokeWidth={1.5} />
    <text x={cx} y={cy - 9} textAnchor="middle" fill={color} fontSize={11} fontWeight="600">
      {payload.atmIV?.toFixed(1)}%
    </text>
  </g>
);

export default function VolTermStructurePanel({ positions, spotPrice }) {
  const [collapsed, setCollapsed] = useState(false);

  const termData = useMemo(
    () => computeTermStructure(positions, spotPrice),
    [positions, spotPrice]
  );

  const termLabel = useMemo(() => {
    if (termData.length < 2) return null;
    const first = termData[0].atmIV;
    const last = termData[termData.length - 1].atmIV;
    const spread = (first - last).toFixed(1);
    const isBackwardation = first > last;
    return {
      isBackwardation,
      label: isBackwardation ? 'Vol Backwardation' : 'Vol Contango',
      spread: `${termData[0].label}-${termData[termData.length - 1].label} spread: ${spread > 0 ? '+' : ''}${spread} vol pts`,
    };
  }, [termData]);

  if (!positions?.length) return null;

  const headerContent = (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 0.7, minHeight: 30 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8, flexWrap: 'wrap', rowGap: 0.45 }}>
        <ShowChartIcon sx={{ fontSize: '1rem', color: alpha(ACCENT, 0.92) }} />
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
          Vol Structure
        </Typography>
        {termLabel && (
          <Chip
            label={termLabel.label}
            size="small"
            sx={{
              bgcolor: termLabel.isBackwardation ? alpha('#ef4444', 0.16) : alpha('#10b981', 0.17),
              color: termLabel.isBackwardation ? '#f87171' : '#34d399',
              border: `1px solid ${termLabel.isBackwardation ? alpha('#ef4444', 0.45) : alpha('#10b981', 0.45)}`,
              fontSize: '0.63rem',
              height: 21,
              fontWeight: 800,
              '& .MuiChip-label': { px: 0.85, fontFamily: NUMERIC_FONT },
            }}
          />
        )}
        {termLabel && (
          <Typography
            variant="caption"
            sx={{
              color: alpha('#94a3b8', 0.85),
              fontSize: '0.64rem',
              fontWeight: 700,
              letterSpacing: '0.04em',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {termLabel.spread}
          </Typography>
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
        <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 0.85, flex: 1 }}>
          {termData.length < 2 ? (
            <Typography variant="caption" sx={{ color: alpha('#94a3b8', 0.8), fontSize: '0.7rem' }}>
              Need at least 2 expiries with ATM positions to plot term structure.
            </Typography>
          ) : (
            <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
              <LineChart data={termData} margin={{ top: 10, right: 20, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis
                  dataKey="label"
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  axisLine={{ stroke: '#334155' }}
                  tickLine={false}
                />
                <YAxis
                  domain={['auto', 'auto']}
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
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
                  formatter={(val, name) => [`${val?.toFixed(2)}%`, name]}
                />
                <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8', paddingTop: 6 }} />
                <Line
                  type="monotone" dataKey="atmIV" name="ATM IV"
                  stroke="#e2e8f0" strokeWidth={2.5}
                  dot={<CustomDot color="#e2e8f0" />} activeDot={{ r: 6 }}
                />
                {termData.some(d => d.callIV !== null) && (
                  <Line
                    type="monotone" dataKey="callIV" name="Call IV"
                    stroke="#3b82f6" strokeWidth={1.5} strokeDasharray="4 3"
                    dot={{ r: 3, fill: '#3b82f6' }} activeDot={{ r: 5 }}
                  />
                )}
                {termData.some(d => d.putIV !== null) && (
                  <Line
                    type="monotone" dataKey="putIV" name="Put IV"
                    stroke="#ef4444" strokeWidth={1.5} strokeDasharray="4 3"
                    dot={{ r: 3, fill: '#ef4444' }} activeDot={{ r: 5 }}
                  />
                )}
              </LineChart>
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
            ATM band ±5% around spot ${spotPrice?.toLocaleString()}. {termData.length} expiries.
          </Typography>
        </Box>
      )}
    </Paper>
  );
}
