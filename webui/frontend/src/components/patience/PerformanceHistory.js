/**
 * PerformanceHistory — closed card performance metrics and history table.
 * Polls /api/patience/performance every 10s.
 *
 * Created: March 17, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import patienceAPI from './patienceService';

const fmt = (v, d = 2) =>
  v == null ? '—' : v.toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });

const pnlColor = (v) => (v == null ? '#94a3b8' : v > 0 ? '#22c55e' : v < 0 ? '#ef4444' : '#94a3b8');

function MetricCard({ label, value, color, sub }) {
  return (
    <div style={{ background: '#0f172a', borderRadius: 8, padding: '14px 18px', flex: 1, minWidth: 110 }}>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color || '#e2e8f0' }}>{value ?? '—'}</div>
      {sub && <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

export default function PerformanceHistory() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const r = await patienceAPI.getPerformance();
      setData(r.data);
    } catch (e) { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetch();
    const id = setInterval(fetch, 10000);
    return () => clearInterval(id);
  }, [fetch]);

  if (loading) return <div style={{ color: '#64748b', padding: 20 }}>Loading performance...</div>;

  const summary = data?.summary || {};
  const records = data?.records || [];

  const bestPnl = records.reduce((best, r) => (r.pnl != null && (best == null || r.pnl > best) ? r.pnl : best), null);
  const worstPnl = records.reduce((worst, r) => (r.pnl != null && (worst == null || r.pnl < worst) ? r.pnl : worst), null);
  const avgHoldDays = (() => {
    const withDates = records.filter(r => r.triggered_at && r.closed_at);
    if (!withDates.length) return null;
    const avg = withDates.reduce((sum, r) => {
      const ms = new Date(r.closed_at) - new Date(r.triggered_at);
      return sum + ms / 86400000;
    }, 0) / withDates.length;
    return avg.toFixed(1);
  })();

  return (
    <div style={{ color: '#e2e8f0' }}>
      <h4 style={{ color: '#a78bfa', marginTop: 0, marginBottom: 16 }}>Performance History</h4>

      {/* ── Summary metrics ── */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
        <MetricCard
          label="Total Closed"
          value={summary.total_cards ?? 0}
        />
        <MetricCard
          label="Win Rate"
          value={summary.total_cards ? `${summary.win_rate ?? 0}%` : '—'}
          color={summary.win_rate >= 50 ? '#22c55e' : summary.win_rate > 0 ? '#f97316' : '#ef4444'}
          sub={summary.total_cards ? `${summary.wins}W / ${summary.losses}L` : null}
        />
        <MetricCard
          label="Total P&L"
          value={summary.total_pnl != null ? `$${fmt(summary.total_pnl)}` : '—'}
          color={pnlColor(summary.total_pnl)}
        />
        <MetricCard
          label="Avg P&L"
          value={summary.avg_pnl != null ? `$${fmt(summary.avg_pnl)}` : '—'}
          color={pnlColor(summary.avg_pnl)}
          sub="per closed card"
        />
        <MetricCard
          label="Best Trade"
          value={bestPnl != null ? `+$${fmt(bestPnl)}` : '—'}
          color="#22c55e"
        />
        <MetricCard
          label="Worst Trade"
          value={worstPnl != null ? `$${fmt(worstPnl)}` : '—'}
          color={pnlColor(worstPnl)}
        />
        <MetricCard
          label="Avg Hold"
          value={avgHoldDays != null ? `${avgHoldDays}d` : '—'}
          color="#94a3b8"
          sub="trigger → close"
        />
      </div>

      {/* ── Records table ── */}
      {records.length === 0 ? (
        <div style={{ color: '#64748b', fontSize: 13, padding: 20, textAlign: 'center', border: '1px dashed #1e293b', borderRadius: 8 }}>
          No cards yet. Records appear here when cards complete.
        </div>
      ) : (
        <div style={{ background: '#0f172a', borderRadius: 8, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ color: '#64748b', borderBottom: '1px solid #1e293b' }}>
                {['Card', 'Triggered', 'Closed', 'Hold', 'Entry Premium', 'Exit Value', 'P&L', 'Handoff P&L'].map(h => (
                  <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 400, whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((r, i) => {
                const holdDays = r.triggered_at && r.closed_at
                  ? ((new Date(r.closed_at) - new Date(r.triggered_at)) / 86400000).toFixed(1)
                  : null;
                return (
                  <tr key={r.card_id || i} style={{ borderBottom: '1px solid #0f172a' }}>
                    <td style={{ padding: '10px 12px', maxWidth: 160 }}>
                      <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#e2e8f0' }}>
                        {r.card_name}
                      </div>
                      <div style={{ fontSize: 10, color: '#334155' }}>{r.card_id?.slice(0, 8)}…</div>
                    </td>
                    <td style={{ padding: '10px 12px', color: '#64748b', fontSize: 12 }}>
                      {r.triggered_at ? new Date(r.triggered_at).toLocaleDateString('en-IN') : '—'}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#64748b', fontSize: 12 }}>
                      {r.closed_at ? new Date(r.closed_at).toLocaleDateString('en-IN') : '—'}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#64748b', fontSize: 12 }}>
                      {holdDays != null ? `${holdDays}d` : '—'}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#94a3b8' }}>
                      {r.entry_premium != null ? `$${fmt(r.entry_premium)}` : '—'}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#94a3b8' }}>
                      {r.exit_value != null ? `$${fmt(r.exit_value)}` : '—'}
                    </td>
                    <td style={{ padding: '10px 12px', fontWeight: 700, color: pnlColor(r.pnl) }}>
                      {r.pnl != null
                        ? `${r.pnl >= 0 ? '+' : ''}$${fmt(r.pnl)}`
                        : <span style={{ color: '#475569', fontSize: 11 }}>open</span>}
                    </td>
                    <td style={{ padding: '10px 12px', color: pnlColor(r.handoff_pnl) }}>
                      {r.handoff_pnl != null ? `${r.handoff_pnl >= 0 ? '+' : ''}$${fmt(r.handoff_pnl)}` : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
