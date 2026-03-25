/**
 * PerformanceHistory — closed card performance metrics and history table.
 * Polls /api/patience/performance + /api/patience/positions every 10s.
 * Open records show live unrealized P&L from positions endpoint.
 *
 * Created: March 17, 2026
 * Updated: March 22, 2026 — live uPnL for open positions
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
  const [posData, setPosData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [perfRes, posRes] = await Promise.allSettled([
        patienceAPI.getPerformance(),
        patienceAPI.getPositions(),
      ]);
      if (perfRes.status === 'fulfilled') setData(perfRes.value.data);
      if (posRes.status === 'fulfilled') setPosData(posRes.value.data);
    } catch (e) { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 10000);
    return () => clearInterval(id);
  }, [fetchAll]);

  if (loading) return <div style={{ color: '#64748b', padding: 20 }}>Loading performance...</div>;

  const summary = data?.summary || {};
  const records = data?.records || [];

  // Build card_id → live position data from positions endpoint
  const posMap = {};
  (posData?.cards || []).forEach(card => {
    posMap[card.card_id] = {
      upnl: card.card_upnl,
      theta: card.card_theta,
      live: card.live_legs,
      total: card.total_legs,
    };
  });

  // Best/worst: use realized pnl (closed cards)
  const bestPnl  = records.reduce((best,  r) => (r.pnl != null && (best  == null || r.pnl > best)  ? r.pnl : best),  null);
  const worstPnl = records.reduce((worst, r) => (r.pnl != null && (worst == null || r.pnl < worst) ? r.pnl : worst), null);

  // Avg hold: prefer closed cards (triggered→closed); fall back to open (triggered→now)
  const avgHoldDays = (() => {
    const closed = records.filter(r => r.triggered_at && r.closed_at);
    if (closed.length) {
      const avg = closed.reduce((sum, r) => {
        return sum + (new Date(r.closed_at) - new Date(r.triggered_at)) / 86400000;
      }, 0) / closed.length;
      return avg.toFixed(1);
    }
    const open = records.filter(r => r.triggered_at && !r.closed_at);
    if (!open.length) return null;
    const avg = open.reduce((sum, r) => {
      return sum + (Date.now() - new Date(r.triggered_at)) / 86400000;
    }, 0) / open.length;
    return avg.toFixed(1);
  })();

  // Helper: hold duration string for a single record
  const holdStr = r => {
    if (r.triggered_at && r.closed_at) {
      const d = ((new Date(r.closed_at) - new Date(r.triggered_at)) / 86400000).toFixed(1);
      return `${d}d`;
    }
    if (r.triggered_at) {
      const d = ((Date.now() - new Date(r.triggered_at)) / 86400000).toFixed(1);
      return `~${d}d`;  // ~ = still open
    }
    return null;
  };

  // Live portfolio aggregates from positions
  const liveUpnl = posData?.summary?.total_upnl ?? null;
  const liveTheta = posData?.summary?.total_theta ?? null;

  return (
    <div style={{ color: '#e2e8f0' }}>
      <h4 style={{ color: '#a78bfa', marginTop: 0, marginBottom: 16 }}>Performance History</h4>

      {/* ── Summary metrics ── */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
        <MetricCard
          label="Total Closed"
          value={summary.total_cards ?? 0}
          sub={summary.open_cards > 0 ? `${summary.open_cards} open` : null}
        />
        <MetricCard
          label="Win Rate"
          value={summary.total_cards ? `${summary.win_rate ?? 0}%` : '—'}
          color={!summary.total_cards ? '#64748b' : summary.win_rate >= 50 ? '#22c55e' : summary.win_rate > 0 ? '#f97316' : '#ef4444'}
          sub={summary.total_cards ? `${summary.wins}W / ${summary.losses}L` : null}
        />
        <MetricCard
          label="Realized P&L"
          value={summary.total_pnl != null ? `$${fmt(summary.total_pnl)}` : '—'}
          color={pnlColor(summary.total_pnl)}
          sub="closed cards only"
        />
        <MetricCard
          label="Live uPnL"
          value={liveUpnl != null ? `${liveUpnl >= 0 ? '+' : ''}$${fmt(liveUpnl)}` : '—'}
          color={pnlColor(liveUpnl)}
          sub="open positions"
        />
        <MetricCard
          label="Portfolio θ/day"
          value={liveTheta != null ? `$${fmt(liveTheta)}` : '—'}
          color={liveTheta != null ? '#a78bfa' : '#64748b'}
          sub="open positions"
        />
        <MetricCard
          label="Best Trade"
          value={bestPnl != null ? `+$${fmt(bestPnl)}` : '—'}
          color={bestPnl != null ? '#22c55e' : '#64748b'}
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
          sub={records.some(r => r.closed_at) ? 'trigger → close' : 'trigger → now'}
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
                {['Card', 'Triggered', 'Closed', 'Hold', 'Entry Premium', 'Exit Value', 'P&L', 'θ/day', 'Handoff P&L'].map(h => (
                  <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 400, whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((r, i) => {
                const pos = posMap[r.card_id];
                const isOpen = r.pnl == null;
                const hold = holdStr(r);
                return (
                  <tr key={r.card_id || i} style={{ borderBottom: '1px solid #1e293b' }}>
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
                    <td style={{ padding: '10px 12px', color: hold?.startsWith('~') ? '#475569' : '#64748b', fontSize: 12 }}>
                      {hold ?? '—'}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#94a3b8' }}>
                      {r.entry_premium != null ? `$${fmt(r.entry_premium)}` : '—'}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#94a3b8' }}>
                      {r.exit_value != null ? `$${fmt(r.exit_value)}` : '—'}
                    </td>
                    <td style={{ padding: '10px 12px', fontWeight: 700 }}>
                      {!isOpen
                        ? <span style={{ color: pnlColor(r.pnl) }}>{`${r.pnl >= 0 ? '+' : ''}$${fmt(r.pnl)}`}</span>
                        : pos?.upnl != null
                          ? <span style={{ color: pnlColor(pos.upnl) }} title="Live unrealized P&L">
                              {`${pos.upnl >= 0 ? '+' : ''}$${fmt(pos.upnl)}`}
                              <span style={{ color: '#f97316', fontSize: 9, marginLeft: 3 }}>LIVE</span>
                            </span>
                          : <span style={{ color: '#475569', fontSize: 11 }}>open</span>}
                    </td>
                    <td style={{ padding: '10px 12px', color: pos?.theta != null ? '#a78bfa' : '#334155', fontSize: 12 }}>
                      {pos?.theta != null ? `$${fmt(pos.theta)}` : '—'}
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
