/**
 * OITable — Strike Table with PCR, OI Change
 *
 * 6 default columns: Strike | Put OI | Call OI | PCR | Put Chg | Call Chg
 * ATM row highlighted. Heatmap row backgrounds.
 *
 * Props:
 *   data: array of { strike, type, oi, oi_usd, oi_change, exchanges }
 *   atmStrike: number (optional)
 *
 * Created: March 27, 2026
 */

import React, { useMemo } from 'react';

function formatOI(value) {
  if (value == null || isNaN(value)) return '—';
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(0);
}

function formatChange(value) {
  if (value == null || isNaN(value) || value === 0) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${formatOI(value)}`;
}

const cellStyle = {
  padding: '8px 12px',
  textAlign: 'right',
  fontFamily: 'monospace',
  fontSize: '12px',
  borderBottom: '1px solid rgba(51, 65, 85, 0.3)',
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

export default function OITable({ data = [], atmStrike = null }) {
  // Aggregate by strike
  const tableData = useMemo(() => {
    const byStrike = {};
    let maxOI = 0;

    for (const row of data) {
      const s = row.strike;
      if (!byStrike[s]) {
        byStrike[s] = { strike: s, putOI: 0, callOI: 0, putChange: 0, callChange: 0 };
      }
      if (row.type === 'put') {
        byStrike[s].putOI += row.oi || 0;
        byStrike[s].putChange += row.oi_change || 0;
      }
      if (row.type === 'call') {
        byStrike[s].callOI += row.oi || 0;
        byStrike[s].callChange += row.oi_change || 0;
      }
    }

    const rows = Object.values(byStrike).sort((a, b) => a.strike - b.strike);

    // Find max OI for heatmap
    for (const r of rows) {
      maxOI = Math.max(maxOI, r.putOI, r.callOI);
    }

    // Compute PCR for each row
    for (const r of rows) {
      r.pcr = r.callOI > 0 ? (r.putOI / r.callOI) : 0;
      r.maxOI = maxOI;
    }

    return rows;
  }, [data]);

  if (!tableData.length) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        minHeight: '300px', color: '#64748b', fontSize: '14px',
      }}>
        No strike data available
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
      <table style={{
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: '12px',
      }}>
        <thead>
          <tr>
            <th style={{ ...headerStyle, textAlign: 'center' }}>Strike</th>
            <th style={{ ...headerStyle, color: '#4caf50' }}>Put OI</th>
            <th style={{ ...headerStyle, color: '#f44336' }}>Call OI</th>
            <th style={headerStyle}>PCR</th>
            <th style={{ ...headerStyle, color: '#4caf50' }}>Put Chg</th>
            <th style={{ ...headerStyle, color: '#f44336' }}>Call Chg</th>
          </tr>
        </thead>
        <tbody>
          {tableData.map((row) => {
            const isATM = atmStrike && Math.abs(row.strike - atmStrike) <=
              (tableData.length > 1 ? Math.abs(tableData[1].strike - tableData[0].strike) * 0.5 : 500);

            // Heatmap intensity based on total OI
            const totalOI = row.putOI + row.callOI;
            const intensity = row.maxOI > 0 ? Math.min(1, totalOI / row.maxOI) : 0;
            const heatBg = `rgba(59, 130, 246, ${intensity * 0.08})`;

            return (
              <tr key={row.strike} style={{
                backgroundColor: isATM ? 'rgba(96, 165, 250, 0.12)' : heatBg,
                borderLeft: isATM ? '3px solid #60a5fa' : '3px solid transparent',
              }}>
                <td style={{
                  ...cellStyle,
                  textAlign: 'center',
                  fontWeight: isATM ? 700 : 500,
                  color: isATM ? '#60a5fa' : '#e2e8f0',
                }}>
                  {Number(row.strike).toLocaleString()}
                  {isATM && <span style={{ fontSize: '9px', marginLeft: '4px', color: '#60a5fa' }}>ATM</span>}
                </td>
                <td style={{ ...cellStyle, color: row.putOI > 0 ? '#4caf50' : '#475569' }}>
                  {formatOI(row.putOI)}
                </td>
                <td style={{ ...cellStyle, color: row.callOI > 0 ? '#f44336' : '#475569' }}>
                  {formatOI(row.callOI)}
                </td>
                <td style={{
                  ...cellStyle,
                  color: row.pcr > 1 ? '#4caf50' : row.pcr < 1 ? '#f44336' : '#94a3b8',
                }}>
                  {row.pcr > 0 ? row.pcr.toFixed(2) : '—'}
                </td>
                <td style={{
                  ...cellStyle,
                  color: row.putChange > 0 ? '#4caf50' : row.putChange < 0 ? '#ef4444' : '#475569',
                }}>
                  {formatChange(row.putChange)}
                </td>
                <td style={{
                  ...cellStyle,
                  color: row.callChange > 0 ? '#f44336' : row.callChange < 0 ? '#22c55e' : '#475569',
                }}>
                  {formatChange(row.callChange)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
