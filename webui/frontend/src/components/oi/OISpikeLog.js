/**
 * OISpikeLog — Real-time Spike Event Feed
 *
 * Displays spike events from SocketIO + historical from GET /spikes.
 * Severity badges: orange (medium) / red (high).
 *
 * Props:
 *   spikes: array of spike event objects
 *   onLoad: function — called on mount to fetch historical spikes
 *
 * Created: March 27, 2026
 */

import React, { useEffect, useState } from 'react';

const SEVERITY_COLORS = {
  high: { bg: 'rgba(239, 68, 68, 0.15)', border: '#ef4444', text: '#fca5a5' },
  medium: { bg: 'rgba(245, 158, 11, 0.15)', border: '#f59e0b', text: '#fcd34d' },
};

function formatTime(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  } catch {
    return ts;
  }
}

function formatOI(value) {
  if (value == null) return '—';
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return Number(value).toFixed(0);
}

const cellStyle = {
  padding: '8px 10px',
  fontSize: '12px',
  fontFamily: 'monospace',
  borderBottom: '1px solid rgba(51, 65, 85, 0.25)',
  whiteSpace: 'nowrap',
};

const headerStyle = {
  ...cellStyle,
  fontFamily: 'inherit',
  fontWeight: 600,
  color: '#94a3b8',
  fontSize: '11px',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  borderBottom: '2px solid rgba(71, 85, 105, 0.5)',
  position: 'sticky',
  top: 0,
  backgroundColor: 'rgb(15, 23, 42)',
  zIndex: 1,
};

export default function OISpikeLog({ spikes = [] }) {
  if (!spikes.length) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        minHeight: '300px', color: '#64748b', fontSize: '14px', gap: '8px',
      }}>
        <span style={{ fontSize: '32px' }}>🔔</span>
        <span>No spikes detected yet</span>
        <span style={{ fontSize: '12px', color: '#475569' }}>
          Spikes fire when OI changes by ≥15% with ≥$500K notional
        </span>
      </div>
    );
  }

  return (
    <div style={{
      maxHeight: '500px',
      overflow: 'auto',
      borderRadius: '8px',
      border: '1px solid rgba(51, 65, 85, 0.4)',
    }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={headerStyle}>Time</th>
            <th style={headerStyle}>Exchange</th>
            <th style={headerStyle}>Strike</th>
            <th style={headerStyle}>Type</th>
            <th style={{ ...headerStyle, textAlign: 'right' }}>Prev OI</th>
            <th style={{ ...headerStyle, textAlign: 'right' }}>Curr OI</th>
            <th style={{ ...headerStyle, textAlign: 'right' }}>Change</th>
            <th style={{ ...headerStyle, textAlign: 'center' }}>Severity</th>
          </tr>
        </thead>
        <tbody>
          {spikes.map((spike, idx) => {
            const sev = SEVERITY_COLORS[spike.severity] || SEVERITY_COLORS.medium;
            const changePct = spike.change_pct;
            const sign = changePct >= 0 ? '+' : '';
            // Stable composite key — avoids full remount when spikes are prepended.
            // spike.id exists for DB-loaded spikes; ts+strike+exchange covers live ones.
            const rowKey = spike.id
              ? `db-${spike.id}`
              : `${spike.ts}-${spike.strike}-${spike.exchange}-${idx}`;

            return (
              <tr key={rowKey} style={{
                backgroundColor: idx % 2 === 0 ? 'transparent' : 'rgba(15, 23, 42, 0.3)',
              }}>
                <td style={{ ...cellStyle, color: '#94a3b8' }}>{formatTime(spike.ts)}</td>
                <td style={{ ...cellStyle, color: '#e2e8f0', textTransform: 'capitalize' }}>
                  {(spike.exchange || '').replace('_', ' ')}
                </td>
                <td style={{ ...cellStyle, color: '#e2e8f0', fontWeight: 600 }}>
                  {Number(spike.strike).toLocaleString()}
                </td>
                <td style={{
                  ...cellStyle,
                  color: spike.type === 'call' ? '#f44336' : '#4caf50',
                  textTransform: 'uppercase',
                  fontWeight: 600,
                }}>
                  {spike.type}
                </td>
                <td style={{ ...cellStyle, textAlign: 'right', color: '#94a3b8' }}>
                  {formatOI(spike.oi_prev)}
                </td>
                <td style={{ ...cellStyle, textAlign: 'right', color: '#e2e8f0' }}>
                  {formatOI(spike.oi_curr)}
                </td>
                <td style={{
                  ...cellStyle, textAlign: 'right',
                  color: changePct >= 0 ? '#4caf50' : '#ef4444',
                  fontWeight: 600,
                }}>
                  {sign}{changePct?.toFixed(1)}%
                </td>
                <td style={{ ...cellStyle, textAlign: 'center' }}>
                  <span style={{
                    display: 'inline-block',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    fontSize: '10px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    backgroundColor: sev.bg,
                    color: sev.text,
                    border: `1px solid ${sev.border}`,
                  }}>
                    {spike.severity}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
