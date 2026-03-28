/**
 * OITable — Strike Table with PCR, OI Change
 *
 * 6 columns: Strike | Put OI ($) | Call OI ($) | PCR | Put Chg | Call Chg
 * - OI displayed in USD (oi_usd) for trader-readable magnitude ($15M vs "229")
 * - ATM row highlighted + auto-scrolled into view on mount/data change
 * - Heatmap intensity based on USD OI
 *
 * Props:
 *   data: array of { strike, type, oi, oi_usd, oi_change, exchanges }
 *   atmStrike: number (optional)
 *
 * Created: March 27, 2026
 * Revised: March 28, 2026 — USD display, ATM auto-scroll
 */

import { useMemo, useRef, useEffect } from 'react';

function formatUSD(value) {
  if (value == null || isNaN(value) || value === 0) return '—';
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

function formatChange(value) {
  if (value == null || isNaN(value) || value === 0) return '—';
  const sign = value > 0 ? '+' : '';
  if (Math.abs(value) >= 1e3) return `${sign}${(value / 1e3).toFixed(1)}K`;
  return `${sign}${value.toFixed(0)}`;
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
  const containerRef = useRef(null);
  const atmRowRef = useRef(null);

  // Aggregate by strike
  const tableData = useMemo(() => {
    const byStrike = {};
    let maxOI_usd = 0;

    for (const row of data) {
      const s = row.strike;
      if (!byStrike[s]) {
        byStrike[s] = {
          strike: s,
          putOI: 0, callOI: 0,
          putOI_usd: 0, callOI_usd: 0,
          putChange: 0, callChange: 0,
        };
      }
      if (row.type === 'put') {
        byStrike[s].putOI += row.oi || 0;
        byStrike[s].putOI_usd += row.oi_usd || 0;
        byStrike[s].putChange += row.oi_change || 0;
      }
      if (row.type === 'call') {
        byStrike[s].callOI += row.oi || 0;
        byStrike[s].callOI_usd += row.oi_usd || 0;
        byStrike[s].callChange += row.oi_change || 0;
      }
    }

    const rows = Object.values(byStrike).sort((a, b) => a.strike - b.strike);

    // Find max USD OI for heatmap
    for (const r of rows) {
      maxOI_usd = Math.max(maxOI_usd, r.putOI_usd, r.callOI_usd);
    }

    // Compute PCR and attach maxOI_usd for heatmap
    for (const r of rows) {
      r.pcr = r.callOI > 0 ? (r.putOI / r.callOI) : 0;
      r.maxOI_usd = maxOI_usd;
    }

    return rows;
  }, [data]);

  // Auto-scroll ATM row into the center of the visible table area
  useEffect(() => {
    if (!atmRowRef.current || !containerRef.current) return;
    const container = containerRef.current;
    const row = atmRowRef.current;
    // Offset: position the ATM row in the center of the container
    const rowOffsetTop = row.offsetTop;
    const rowHeight = row.clientHeight;
    const containerHeight = container.clientHeight;
    container.scrollTop = rowOffsetTop - containerHeight / 2 + rowHeight / 2;
  }, [atmStrike, tableData.length]);

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

  // Strike interval for ATM proximity check
  const strikeInterval = tableData.length > 1
    ? Math.abs(tableData[1].strike - tableData[0].strike)
    : 500;

  return (
    <div
      ref={containerRef}
      style={{
        maxHeight: '500px',
        overflow: 'auto',
        borderRadius: '8px',
        border: '1px solid rgba(51, 65, 85, 0.4)',
      }}
    >
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
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
            const isATM = atmStrike != null &&
              Math.abs(row.strike - atmStrike) <= strikeInterval * 0.5;

            // Heatmap: intensity based on USD OI
            const totalOI_usd = row.putOI_usd + row.callOI_usd;
            const intensity = row.maxOI_usd > 0
              ? Math.min(1, totalOI_usd / row.maxOI_usd)
              : 0;
            const heatBg = `rgba(59, 130, 246, ${intensity * 0.08})`;

            return (
              <tr
                key={row.strike}
                ref={isATM ? atmRowRef : null}
                style={{
                  backgroundColor: isATM ? 'rgba(96, 165, 250, 0.12)' : heatBg,
                  borderLeft: isATM ? '3px solid #fbbf24' : '3px solid transparent',
                }}
              >
                <td style={{
                  ...cellStyle,
                  textAlign: 'center',
                  fontWeight: isATM ? 700 : 500,
                  color: isATM ? '#fbbf24' : '#e2e8f0',
                }}>
                  {Number(row.strike).toLocaleString()}
                  {isATM && (
                    <span style={{ fontSize: '9px', marginLeft: '4px', color: '#fbbf24' }}>
                      ATM
                    </span>
                  )}
                </td>
                <td style={{ ...cellStyle, color: row.putOI_usd > 0 ? '#4caf50' : '#475569' }}>
                  {formatUSD(row.putOI_usd)}
                </td>
                <td style={{ ...cellStyle, color: row.callOI_usd > 0 ? '#f44336' : '#475569' }}>
                  {formatUSD(row.callOI_usd)}
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