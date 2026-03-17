/**
 * PnLDashboard — P&L summary + performance history across all Patience cards.
 * Polls /api/patience/pnl (active) and /api/patience/performance (closed) every 5s.
 *
 * Created: March 14, 2026
 * Rebuilt: March 17, 2026 — full P&L, performance metrics, win rate
 */

import React, { useState, useEffect, useCallback } from 'react';
import patienceAPI from './patienceService';

const fmt = (v, decimals = 2) =>
  v == null ? '—' : v.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

const pnlColor = (v) => (v == null ? '#94a3b8' : v > 0 ? '#22c55e' : v < 0 ? '#ef4444' : '#94a3b8');

const STATUS_COLORS = {
  DRAFT: '#9ca3af', WAITING: '#a78bfa', ARMED: '#3b82f6',
  TRIGGERED: '#f97316', EXECUTING: '#eab308',
  COMPLETED: '#22c55e', PAUSED: '#ef4444', CANCELLED: '#6b7280',
};

function StatusBadge({ status }) {
  return (
    <span style={{
      padding: '2px 8px', borderRadius: 10,
      background: STATUS_COLORS[status] || '#9ca3af',
      color: '#000', fontSize: 11, fontWeight: 700,
    }}>
      {status}
    </span>
  );
}

function MetricTile({ label, value, unit, color, subtext }) {
  return (
    <div style={{ background: '#0f172a', borderRadius: 8, padding: '14px 18px', minWidth: 120, flex: 1 }}>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color || '#e2e8f0' }}>
        {value == null ? '—' : value}
        {unit && value != null && <span style={{ fontSize: 12, color: '#64748b', marginLeft: 4 }}>{unit}</span>}
      </div>
      {subtext && <div style={{ fontSize: 11, color: '#475569', marginTop: 3 }}>{subtext}</div>}
    </div>
  );
}

export default function PnLDashboard() {
  const [pnlData, setPnlData] = useState(null);
  const [perfData, setPerfData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('active');

  const fetchAll = useCallback(async () => {
    try {
      const [pnlRes, perfRes] = await Promise.all([
        patienceAPI.getPnL(),
        patienceAPI.getPerformance(),
      ]);
      setPnlData(pnlRes.data);
      setPerfData(perfRes.data);
    } catch (e) { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 5000);
    return () => clearInterval(id);
  }, [fetchAll]);

  if (loading) return <div style={{ color: '#64748b', padding: 20 }}>Loading P&L...</div>;

  const activeCards = pnlData?.cards || [];
  const perfRecords = perfData?.records || [];
  const perfSummary = perfData?.summary || {};

  // Aggregate active P&L
  const totalEntryPremium = activeCards.reduce((s, c) => s + (c.entry_premium || 0), 0);
  const activeCount = activeCards.filter(c => c.status === 'EXECUTING').length;
  const completedCount = activeCards.filter(c => c.status === 'COMPLETED').length;

  return (
    <div style={{ color: '#e2e8f0' }}>
      <h4 style={{ color: '#a78bfa', marginTop: 0, marginBottom: 16 }}>Patience P&L</h4>

      {/* ── Performance summary row ── */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        <MetricTile
          label="Total Closed"
          value={perfSummary.total_cards ?? 0}
          color="#e2e8f0"
        />
        <MetricTile
          label="Win Rate"
          value={perfSummary.total_cards ? `${perfSummary.win_rate ?? 0}%` : '—'}
          color={perfSummary.win_rate >= 50 ? '#22c55e' : '#ef4444'}
          subtext={perfSummary.total_cards ? `${perfSummary.wins}W / ${perfSummary.losses}L` : null}
        />
        <MetricTile
          label="Total P&L"
          value={perfSummary.total_pnl != null ? `$${fmt(perfSummary.total_pnl)}` : '—'}
          color={pnlColor(perfSummary.total_pnl)}
        />
        <MetricTile
          label="Avg P&L / Card"
          value={perfSummary.avg_pnl != null ? `$${fmt(perfSummary.avg_pnl)}` : '—'}
          color={pnlColor(perfSummary.avg_pnl)}
        />
        <MetricTile
          label="Active"
          value={activeCount}
          color="#eab308"
          subtext={`${completedCount} completed`}
        />
        <MetricTile
          label="Premium Deployed"
          value={totalEntryPremium ? `$${fmt(totalEntryPremium)}` : '—'}
          color="#94a3b8"
        />
      </div>

      {/* ── Tabs ── */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 12, borderBottom: '1px solid #1e293b' }}>
        {['active', 'history'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              padding: '8px 16px', fontSize: 13, fontWeight: 600,
              color: tab === t ? '#a78bfa' : '#64748b',
              borderBottom: tab === t ? '2px solid #a78bfa' : '2px solid transparent',
            }}
          >
            {t === 'active' ? `Active Cards (${activeCards.length})` : `History (${perfRecords.length})`}
          </button>
        ))}
      </div>

      {tab === 'active' && (
        <ActiveCardsTable cards={activeCards} />
      )}

      {tab === 'history' && (
        <HistoryTable records={perfRecords} />
      )}
    </div>
  );
}

function ActiveCardsTable({ cards }) {
  if (cards.length === 0) {
    return <div style={{ color: '#64748b', fontSize: 13, padding: 12 }}>No active cards.</div>;
  }
  return (
    <div style={{ background: '#0f172a', borderRadius: 8, overflow: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ color: '#64748b', background: '#0f172a', borderBottom: '1px solid #1e293b' }}>
            {['Card', 'Status', 'Legs', 'Entry Premium', 'Current Value', 'Unrealized P&L', 'MMM Handoffs'].map(h => (
              <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 400, whiteSpace: 'nowrap' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cards.map(c => (
            <tr key={c.card_id} style={{ borderBottom: '1px solid #1e293b' }}>
              <td style={{ padding: '10px 12px', maxWidth: 160 }}>
                <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#e2e8f0' }}>
                  {c.card_name}
                </div>
                <div style={{ fontSize: 10, color: '#475569' }}>{c.card_id?.slice(0, 8)}…</div>
              </td>
              <td style={{ padding: '10px 12px' }}><StatusBadge status={c.status} /></td>
              <td style={{ padding: '10px 12px', color: '#94a3b8', textAlign: 'center' }}>
                {c.filled_count ?? 0}/{c.legs_count ?? 0}
              </td>
              <td style={{ padding: '10px 12px', color: '#94a3b8' }}>
                {c.entry_premium != null && c.entry_premium !== 0 ? `$${fmt(c.entry_premium)}` : '—'}
              </td>
              <td style={{ padding: '10px 12px', color: '#64748b', fontSize: 12 }}>
                {c.current_value != null ? `$${fmt(c.current_value)}` : <span style={{ color: '#334155' }}>live N/A</span>}
              </td>
              <td style={{ padding: '10px 12px', color: pnlColor(c.unrealized_pnl) }}>
                {c.unrealized_pnl != null
                  ? `${c.unrealized_pnl >= 0 ? '+' : ''}$${fmt(c.unrealized_pnl)}`
                  : <span style={{ color: '#334155', fontSize: 12 }}>—</span>}
              </td>
              <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                {c.mmm_legs > 0
                  ? <span style={{ color: '#a78bfa', fontSize: 11 }}>🔄 {c.mmm_legs}</span>
                  : <span style={{ color: '#334155' }}>—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HistoryTable({ records }) {
  if (records.length === 0) {
    return <div style={{ color: '#64748b', fontSize: 13, padding: 12 }}>No closed cards yet.</div>;
  }
  return (
    <div style={{ background: '#0f172a', borderRadius: 8, overflow: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ color: '#64748b', background: '#0f172a', borderBottom: '1px solid #1e293b' }}>
            {['Card', 'Closed At', 'Entry Premium', 'Exit Value', 'P&L', 'Handoff P&L'].map(h => (
              <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 400, whiteSpace: 'nowrap' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {records.map((r, i) => (
            <tr key={r.card_id || i} style={{ borderBottom: '1px solid #1e293b' }}>
              <td style={{ padding: '10px 12px', maxWidth: 160 }}>
                <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#e2e8f0' }}>
                  {r.card_name}
                </div>
                <div style={{ fontSize: 10, color: '#475569' }}>{r.card_id?.slice(0, 8)}…</div>
              </td>
              <td style={{ padding: '10px 12px', color: '#64748b', fontSize: 12 }}>
                {r.closed_at ? new Date(r.closed_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' }) : '—'}
              </td>
              <td style={{ padding: '10px 12px', color: '#94a3b8' }}>
                {r.entry_premium != null ? `$${fmt(r.entry_premium)}` : '—'}
              </td>
              <td style={{ padding: '10px 12px', color: '#94a3b8' }}>
                {r.exit_value != null ? `$${fmt(r.exit_value)}` : '—'}
              </td>
              <td style={{ padding: '10px 12px', fontWeight: 600, color: pnlColor(r.pnl) }}>
                {r.pnl != null ? `${r.pnl >= 0 ? '+' : ''}$${fmt(r.pnl)}` : '—'}
              </td>
              <td style={{ padding: '10px 12px', color: pnlColor(r.handoff_pnl) }}>
                {r.handoff_pnl != null ? `${r.handoff_pnl >= 0 ? '+' : ''}$${fmt(r.handoff_pnl)}` : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
