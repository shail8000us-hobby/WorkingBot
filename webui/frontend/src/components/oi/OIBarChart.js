/**
 * OIBarChart — Absolute Open Interest by Strike
 *
 * Recharts BarChart showing total OI per strike, grouped by Put/Call.
 * Green bars = Puts, Red bars = Calls (matching OI Aggregator plan).
 *
 * Props:
 *   data: array of { strike, type, oi, oi_usd, oi_change, exchanges }
 *   atmStrike: number (optional, for ATM reference line)
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
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color, display: 'flex', gap: '8px', marginTop: '2px' }}>
          <span>{p.name}:</span>
          <span style={{ fontWeight: 600, fontFamily: 'monospace' }}>{formatOI(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

export default function OIBarChart({ data = [], atmStrike = null }) {
  // Transform row-per-type data into chart-friendly format
  const chartData = useMemo(() => {
    const byStrike = {};
    for (const row of data) {
      const s = row.strike;
      if (!byStrike[s]) {
        byStrike[s] = { strike: s, putOI: 0, callOI: 0 };
      }
      if (row.type === 'put') byStrike[s].putOI += row.oi;
      if (row.type === 'call') byStrike[s].callOI += row.oi;
    }
    return Object.values(byStrike).sort((a, b) => a.strike - b.strike);
  }, [data]);

  if (!chartData.length) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        minHeight: '300px', color: '#64748b', fontSize: '14px',
      }}>
        No OI data available — waiting for first fetch cycle
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
        {atmStrike && (
          <ReferenceLine
            x={atmStrike}
            stroke="#60a5fa"
            strokeWidth={2}
            strokeDasharray="4 4"
            label={{
              value: `ATM ${formatStrike(atmStrike)}`,
              position: 'top',
              fill: '#60a5fa',
              fontSize: 10,
              fontWeight: 600,
            }}
          />
        )}
        <Bar
          dataKey="putOI"
          name="Put OI"
          fill={COLORS.put}
          fillOpacity={0.85}
          radius={[2, 2, 0, 0]}
          maxBarSize={24}
        />
        <Bar
          dataKey="callOI"
          name="Call OI"
          fill={COLORS.call}
          fillOpacity={0.85}
          radius={[2, 2, 0, 0]}
          maxBarSize={24}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
