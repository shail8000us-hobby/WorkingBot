/**
 * ICPayoffDiagram — Payoff at expiry chart
 * X = BTC price, Y = P&L in USD
 */
import React, { useMemo } from 'react';
import { Box, Typography } from '@mui/material';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip as RechartsTooltip, ReferenceLine,
} from 'recharts';

const ICPayoffDiagram = ({ session }) => {
  const cycle = session?.current_cycle;

  const chartData = useMemo(() => {
    if (!cycle?.legs) return [];

    const legs = cycle.legs;
    const lp = legs.lp?.strike || 0;
    const sp = legs.sp?.strike || 0;
    const sc = legs.sc?.strike || 0;
    const lc = legs.lc?.strike || 0;
    const netCredit = cycle.net_credit || 0;
    const wingWidth = (sp - lp) || 1000;
    const maxLoss = wingWidth - netCredit;

    if (!lp || !sp || !sc || !lc) return [];

    const points = [];
    const lo = lp - wingWidth;
    const hi = lc + wingWidth;
    const step = (hi - lo) / 100;

    for (let price = lo; price <= hi; price += step) {
      let pnl;
      if (price <= lp) {
        pnl = -maxLoss;
      } else if (price <= sp) {
        pnl = -maxLoss + ((price - lp) / (sp - lp)) * (netCredit + maxLoss);
      } else if (price <= sc) {
        pnl = netCredit;
      } else if (price <= lc) {
        pnl = netCredit - ((price - sc) / (lc - sc)) * (netCredit + maxLoss);
      } else {
        pnl = -maxLoss;
      }
      points.push({ price: Math.round(price), pnl: parseFloat(pnl.toFixed(4)) });
    }
    return points;
  }, [cycle]);

  if (!cycle?.legs || chartData.length === 0) {
    return <Box sx={{ p: 3, textAlign: 'center' }}><Typography color="text.secondary">No active cycle for payoff diagram</Typography></Box>;
  }

  const legs = cycle.legs;
  const netCredit = cycle.net_credit || 0;
  const spot = session.spot_price || session.last_spot || 0;
  const wingWidth = (legs.sp?.strike - legs.lp?.strike) || 1000;
  const maxLoss = wingWidth - netCredit;

  return (
    <Box sx={{ p: 1 }}>
      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
        Payoff at Expiry
      </Typography>

      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={chartData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
          <defs>
            <linearGradient id="icPayoffGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#4caf50" stopOpacity={0.3} />
              <stop offset="50%" stopColor="#4caf50" stopOpacity={0} />
              <stop offset="95%" stopColor="#f44336" stopOpacity={0.2} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="price" type="number" domain={['dataMin', 'dataMax']}
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
            stroke="rgba(255,255,255,0.3)" tick={{ fontSize: 10 }}
          />
          <YAxis
            tickFormatter={(v) => `$${v.toFixed(0)}`}
            stroke="rgba(255,255,255,0.3)" tick={{ fontSize: 10 }}
          />
          <RechartsTooltip
            formatter={(v) => [`$${v.toFixed(4)}`, 'P&L']}
            labelFormatter={(v) => `BTC: $${v.toLocaleString()}`}
            contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 4 }}
          />

          {/* Reference lines */}
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.3)" strokeDasharray="3 3" />
          <ReferenceLine y={netCredit} stroke="#4caf50" strokeDasharray="3 3" label={{ value: 'Max Profit', fill: '#4caf50', fontSize: 10 }} />
          <ReferenceLine y={-maxLoss} stroke="#f44336" strokeDasharray="3 3" label={{ value: 'Max Loss', fill: '#f44336', fontSize: 10 }} />
          {spot > 0 && <ReferenceLine x={spot} stroke="#ff9800" strokeDasharray="3 3" label={{ value: 'NOW', fill: '#ff9800', fontSize: 10 }} />}

          <Area type="monotone" dataKey="pnl" stroke="#64b5f6" fill="url(#icPayoffGrad)" strokeWidth={2} dot={false} />
        </AreaChart>
      </ResponsiveContainer>

      <Box sx={{ display: 'flex', justifyContent: 'space-around', mt: 1 }}>
        {[
          { label: 'LP', val: legs.lp?.strike },
          { label: 'SP', val: legs.sp?.strike },
          { label: 'NOW', val: spot, color: '#ff9800' },
          { label: 'SC', val: legs.sc?.strike },
          { label: 'LC', val: legs.lc?.strike },
        ].map((s) => (
          <Typography key={s.label} variant="caption" sx={{ fontFamily: 'monospace', color: s.color || 'text.secondary', fontWeight: 600, fontSize: '0.7rem' }}>
            {s.label}: ${(s.val || 0).toLocaleString()}
          </Typography>
        ))}
      </Box>
    </Box>
  );
};

export default ICPayoffDiagram;
