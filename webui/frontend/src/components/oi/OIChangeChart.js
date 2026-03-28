/**
 * OIChangeChart — OI Change by Strike
 *
 * Recharts BarChart showing OI change (delta) per strike.
 * Positive values go up, negative go down.
 * Green = Puts, Red = Calls (matching plan).
 *
 * Props:
 *   data: array of { strike, type, oi_change, oi, exchanges }
 *   atmStrike: number (optional)
 *
 * Created: March 27, 2026
 */

import React, { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';

const COLORS = {
  put: '#4caf50',
  call: '#f44336',
};

function formatOI(value) {
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(0);
}

function formatStrike(val) {
  if (val >= 1000) return `${(val / 1000).toFixed(0)}K`;
  return val.toString();
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;

  return (
    <div style={{
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      border: '1px solid rgba(71, 85, 105, 0.6)',
      borderRadius: '8px',
      padding: '10px 14px',
      fontSize: '12px',
      backdropFilter: 'blur(8px)',
    }}>
      <div style={{ color: '#e2e8f0', fontWeight: 600, marginBottom: '6px' }}>
        Strike: {Number(label).toLocaleString()}
      </div>
      {payload.map((p, i) => {
        const sign = p.value >= 0 ? '+' : '';
        return (
          <div key={i} style={{ color: p.color, display: 'flex', gap: '8px', marginTop: '2px' }}>
            <span>{p.name}:</span>
            <span style={{ fontWeight: 600, fontFamily: 'monospace' }}>
              {sign}{formatOI(p.value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function OIChangeChart({ data = [], atmStrike = null }) {
  const chartData = useMemo(() => {
    const byStrike = {};
    for (const row of data) {
      const s = row.strike;
      if (!byStrike[s]) {
        byStrike[s] = { strike: s, putChange: 0, callChange: 0 };
      }
      if (row.type === 'put') byStrike[s].putChange += (row.oi_change || 0);
      if (row.type === 'call') byStrike[s].callChange += (row.oi_change || 0);
    }
    return Object.values(byStrike).sort((a, b) => a.strike - b.strike);
  }, [data]);

  // Show waiting state if no data at all, OR if all changes are zero
  // (system is on first cycle — no baseline yet for comparison)
  const hasAnyChange = chartData.some(d => d.putChange !== 0 || d.callChange !== 0);

  if (!chartData.length || !hasAnyChange) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        minHeight: '300px', color: '#64748b', fontSize: '14px',
      }}>
        {chartData.length === 0
          ? 'No OI data available — waiting for first fetch cycle'
          : 'Waiting for baseline — OI change visible after 2nd fetch cycle (~60s)'}
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={360}>
      <BarChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" vertical={false} />
        <XAxis
          dataKey="strike"
          tickFormatter={formatStrike}
          tick={{ fill: '#94a3b8', fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: 'rgba(148, 163, 184, 0.15)' }}
          interval="preserveStartEnd"
        />
        <YAxis
          tickFormatter={formatOI}
          tick={{ fill: '#94a3b8', fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={55}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }}
          iconType="square"
        />
        {/* Zero baseline */}
        <ReferenceLine
          y={0}
          stroke="rgba(255, 255, 255, 0.2)"
          strokeWidth={1}
        />
        {atmStrike && (
          <ReferenceLine
            x={atmStrike}
            stroke="#fbbf24"
            strokeWidth={2}
            strokeDasharray="5 3"
            label={{
              value: `▼ ATM ${formatStrike(atmStrike)}`,
              position: 'insideTopRight',
              fill: '#fbbf24',
              fontSize: 12,
              fontWeight: 700,
            }}
          />
        )}
        {/* radius={[2,2,0,0]} only applies to positive bars (rounded top).
            Recharts does not flip radius for negative bars, so we leave
            bottom corners flat — this is consistent for both directions. */}
        <Bar
          dataKey="putChange"
          name="Put Chg"
          fill={COLORS.put}
          fillOpacity={0.85}
          radius={[2, 2, 0, 0]}
          maxBarSize={24}
        />
        <Bar
          dataKey="callChange"
          name="Call Chg"
          fill={COLORS.call}
          fillOpacity={0.85}
          radius={[2, 2, 0, 0]}
          maxBarSize={24}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
