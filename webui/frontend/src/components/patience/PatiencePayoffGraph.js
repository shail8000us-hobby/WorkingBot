/**
 * PatiencePayoffGraph — Payoff visualization for Patience card legs
 *
 * Lightweight component that reuses existing payoff calculator logic to show
 * the expected P&L curve for a card's legs.
 *
 * Created: March 14, 2026
 */

import React, { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Area, ComposedChart } from 'recharts';

const CONTRACT_MULTIPLIER = 0.001; // BTC standard on Delta Exchange

function parseExpiryDate(expiryStr) {
  // YYYY-MM-DD → Date
  const parts = expiryStr.split('-');
  const year = parseInt(parts[0]);
  const month = parseInt(parts[1]) - 1;
  const day = parseInt(parts[2]);
  return new Date(Date.UTC(year, month, day, 0, 0, 0));
}

function calculateDaysToExpiry(expiryDate) {
  const now = new Date();
  const msToExpiry = expiryDate - now;
  return Math.max(0, msToExpiry / (1000 * 60 * 60 * 24));
}

function calculatePayoff(legs, prices, spotPrice, priceRange = 0.15) {
  if (!legs || legs.length === 0) return { data: [], spotPrice: 90000 };

  const minPrice = spotPrice * (1 - priceRange);
  const maxPrice = spotPrice * (1 + priceRange);
  const numPoints = 100;
  const priceStep = (maxPrice - minPrice) / numPoints;

  const data = [];

  for (let i = 0; i <= numPoints; i++) {
    const price = minPrice + i * priceStep;
    let payoff = 0;

    legs.forEach((leg) => {
      const legPrice = prices.find(p => p.leg_id === leg.leg_id);
      const strike = parseFloat(leg.strike || 0);
      const lots = parseFloat(leg.lots || 0);
      const direction = leg.direction === 'BUY' ? 1 : -1;
      const optionType = leg.option_type === 'CE' ? 'call' : 'put';

      // Entry price: use mid from prices, or 0 if not available
      const bid = legPrice?.bid || 0;
      const ask = legPrice?.ask || 0;
      const entryPrice = (bid && ask) ? (bid + ask) / 2 : (legPrice?.mark_price || 0);

      // Calculate intrinsic value at expiry
      const intrinsic = optionType === 'call'
        ? Math.max(0, price - strike)
        : Math.max(0, strike - price);

      // P&L for this leg: (intrinsic - entryPrice) * lots * multiplier * direction
      const legPnl = (intrinsic - entryPrice) * lots * CONTRACT_MULTIPLIER * direction;
      payoff += legPnl;
    });

    data.push({
      price: Math.round(price),
      payoff: Math.round(payoff),
      payoffGreen: payoff >= 0 ? payoff : null,
      payoffRed: payoff < 0 ? payoff : null,
    });
  }

  return { data, spotPrice };
}

export default function PatiencePayoffGraph({ legs, prices, spotPrice }) {
  const { data, spotPrice: actualSpot } = useMemo(() => {
    return calculatePayoff(legs, prices, spotPrice || 90000);
  }, [legs, prices, spotPrice]);

  if (!data || data.length === 0) {
    return (
      <div style={{ padding: 20, color: '#64748b', fontSize: 13, textAlign: 'center' }}>
        No data available for payoff graph
      </div>
    );
  }

  const maxProfit = Math.max(...data.map(d => d.payoff));
  const maxLoss = Math.min(...data.map(d => d.payoff));

  return (
    <div style={{ width: '100%', background: '#0a0f1a', borderRadius: 8, padding: 16 }}>
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: 13, color: '#a78bfa', fontWeight: 600 }}>Payoff at Expiry</div>
        <div style={{ fontSize: 11, color: '#64748b' }}>
          Max Gain: <span style={{ color: '#22c55e', fontWeight: 600 }}>${maxProfit.toLocaleString()}</span>
          {' · '}
          Max Loss: <span style={{ color: '#ef4444', fontWeight: 600 }}>${maxLoss.toLocaleString()}</span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="price"
            stroke="#64748b"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            tickFormatter={(val) => `$${(val / 1000).toFixed(0)}k`}
          />
          <YAxis
            stroke="#64748b"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            tickFormatter={(val) => `$${val.toLocaleString()}`}
          />
          <Tooltip
            contentStyle={{
              background: '#0f172a',
              border: '1px solid #1e293b',
              borderRadius: 4,
              fontSize: 12,
              color: '#e2e8f0',
            }}
            labelStyle={{ color: '#a78bfa', fontWeight: 600 }}
            formatter={(value, name) => [`$${value.toLocaleString()}`, name === 'payoff' ? 'P&L' : name]}
            labelFormatter={(label) => `BTC @ $${label.toLocaleString()}`}
          />
          <ReferenceLine y={0} stroke="#475569" strokeWidth={2} />
          <ReferenceLine x={actualSpot} stroke="#a78bfa" strokeWidth={1} strokeDasharray="3 3" />
          <Area type="monotone" dataKey="payoffGreen" fill="#22c55e" fillOpacity={0.3} stroke="none" />
          <Area type="monotone" dataKey="payoffRed" fill="#ef4444" fillOpacity={0.3} stroke="none" />
          <Line
            type="monotone"
            dataKey="payoff"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      <div style={{ marginTop: 8, fontSize: 10, color: '#475569', textAlign: 'center' }}>
        Current Spot: <span style={{ color: '#a78bfa', fontWeight: 600 }}>${actualSpot.toLocaleString()}</span>
        {' · '}
        Graph shows intrinsic value at expiry (no time premium)
      </div>
    </div>
  );
}
