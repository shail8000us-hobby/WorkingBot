/**
 * PnLDashboard — P&L summary across all Patience cards.
 * Polls /api/patience/pnl every 5s.
 *
 * Created: March 14, 2026
 */

import React, { useState, useEffect } from 'react';
import patienceAPI from './patienceService';

const fmt = (v, decimals = 2) =>
  v == null ? '—' : v.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

const pnlColor = (v) => (v == null ? '#94a3b8' : v >= 0 ? '#22c55e' : '#ef4444');

export default function PnLDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const r = await patienceAPI.getPnL();
        setData(r.data);
      } catch (e) { /* silent */ }
      finally { setLoading(false); }
    };
    fetch();
    const id = setInterval(fetch, 5000);
    return () => clearInterval(id);
  }, []);

  if (loading) return <div style={{ color: '#64748b', padding: 20 }}>Loading P&L...</div>;
  if (!data) return <div style={{ color: '#ef4444', padding: 20 }}>Failed to load P&L data.</div>;

  const { cards = [] } = data;

  // Calculate summary from cards (backend doesn't return summary)
  const summary = {
    total_cards: cards.length,
    active_cards: cards.filter(c => c.status === 'EXECUTING').length,
    completed_cards: cards.filter(c => c.status === 'COMPLETED').length,
  };

  return (
    <div style={{ color: '#e2e8f0' }}>
      <h4 style={{ color: '#a78bfa', marginTop: 0 }}>Patience P&L Summary</h4>

      {/* Summary tiles */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <SummaryTile label="Total Cards" value={summary.total_cards} plain />
        <SummaryTile label="Completed" value={summary.completed_cards} plain />
        <SummaryTile label="Active" value={summary.active_cards} plain />
      </div>

      {/* Per-card table */}
      {cards.length === 0 ? (
        <div style={{ color: '#64748b', fontSize: 13 }}>No cards with P&L data yet.</div>
      ) : (
        <div style={{ background: '#0f172a', borderRadius: 8, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ color: '#64748b', background: '#0f172a', borderBottom: '1px solid #1e293b' }}>
                {['Card', 'Status', 'Entry Premium', 'Unrealized P&L', 'Legs', 'Handoffs'].map(h => (
                  <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 400 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cards.map(c => (
                <tr key={c.card_id} style={{ borderBottom: '1px solid #1e293b' }}>
                  <td style={{ padding: '10px 12px', color: '#e2e8f0', maxWidth: 160 }}>
                    <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {c.card_name}
                    </div>
                    <div style={{ fontSize: 10, color: '#475569' }}>{c.card_id?.slice(0, 8)}...</div>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <StatusBadge status={c.status} />
                  </td>
                  <td style={{ padding: '10px 12px', color: '#94a3b8' }}>
                    {c.entry_premium != null ? `$${fmt(c.entry_premium)}` : '—'}
                  </td>
                  <td style={{ padding: '10px 12px', color: pnlColor(c.unrealized_pnl) }}>
                    {c.unrealized_pnl != null ? `$${fmt(c.unrealized_pnl)}` : '—'}
                  </td>
                  <td style={{ padding: '10px 12px', color: '#94a3b8', textAlign: 'center' }}>
                    {c.filled_count ?? '—'} / {c.legs_count ?? '—'}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                    {c.mmm_legs > 0 ? (
                      <span style={{ color: '#a78bfa', fontSize: 11 }}>🔄 {c.mmm_legs}</span>
                    ) : (
                      <span style={{ color: '#475569' }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ fontSize: 11, color: '#475569', marginTop: 12 }}>
        P&L is approximate. Unrealized values use last fill price as reference. MMM-handed legs tracked separately.
      </div>
    </div>
  );
}

function SummaryTile({ label, value, unit, plain }) {
  const isNum = !plain && typeof value === 'number';
  const color = isNum ? pnlColor(value) : '#e2e8f0';
  const display = value == null ? '—' : plain ? value : `${value >= 0 ? '+' : ''}$${fmt(value)}`;
  return (
    <div style={{ background: '#0f172a', borderRadius: 8, padding: '14px 20px', minWidth: 120, textAlign: 'center' }}>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>
        {display}
        {unit && value != null && <span style={{ fontSize: 12, color: '#64748b', marginLeft: 4 }}>{unit}</span>}
      </div>
    </div>
  );
}

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
