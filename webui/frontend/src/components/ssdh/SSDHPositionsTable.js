/**
 * SSDHPositionsTable — Per-leg panel showing entry price, current price, and P&L bar
 */
import React from 'react';

function fmtP(v) { return v != null ? `$${Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '—'; }
function fmtBtc(v) { if (v == null) return '—'; return `${v >= 0 ? '+' : ''}${v.toFixed(4)}`; }

function LegRow({ pos, structureBroken }) {
  const isShort  = pos.direction === 'short';
  const pnl      = pos.unrealized_pnl ?? 0;
  const entry    = pos.entry_premium;
  const current  = pos.current_premium;
  const isClosed = pos.status === 'closed';

  // For short legs: profit when current < entry. For long: profit when current > entry.
  const maxMove = entry * 2 || 1;
  const profit  = isShort ? (entry - (current ?? entry)) : ((current ?? entry) - entry);
  const barPct  = Math.min(100, Math.max(0, (profit / maxMove) * 100));
  const barColor = structureBroken ? '#ef4444' : pnl >= 0 ? '#22c55e' : '#ef4444';

  const dirColor = isShort ? '#fca5a5' : '#86efac';
  const dirBg    = isShort ? '#450a0a' : '#052e16';
  const dirBorder= isShort ? '#dc2626' : '#16a34a';

  return (
    <div style={{
      background: structureBroken ? '#3b0000' : dirBg,
      border: `1px solid ${structureBroken ? '#7f1d1d' : dirBorder}`,
      borderRadius: 6,
      padding: '10px 14px',
      opacity: isClosed ? 0.5 : 1,
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div>
          <span style={{ color: dirColor, fontWeight: 700, fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            {isShort ? 'SHORT' : 'LONG'} {pos.side}
          </span>
          <span style={{ color: '#6b7280', fontSize: 11, marginLeft: 8 }}>
            {pos.pos_type === 'core' ? 'ATM' : 'OTM'} • {pos.lots} lot{pos.lots > 1 ? 's' : ''}
          </span>
        </div>
        <span style={{ fontFamily: 'monospace', fontWeight: 700, color: pnl >= 0 ? '#22c55e' : '#ef4444', fontSize: 14 }}>
          {fmtBtc(pnl)} BTC
        </span>
      </div>

      {/* Strike + price bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ color: '#f9fafb', fontFamily: 'monospace', fontWeight: 700, fontSize: 14 }}>K = {fmtP(pos.strike)}</span>
        <span style={{ color: '#9ca3af', fontSize: 12 }}>
          {fmtP(entry)} → <span style={{ color: current != null ? '#f9fafb' : '#6b7280' }}>{fmtP(current)}</span>
        </span>
      </div>

      {/* P&L progress bar */}
      <div style={{ background: '#1f2937', borderRadius: 3, height: 4 }}>
        <div style={{ width: `${barPct}%`, background: barColor, height: '100%', borderRadius: 3, transition: 'width 0.8s' }} />
      </div>

      {isClosed && <div style={{ color: '#6b7280', fontSize: 10, marginTop: 4 }}>CLOSED • {pos.close_reason}</div>}
    </div>
  );
}

export default function SSDHPositionsTable({ positions = [], structureOk = true }) {
  if (!positions.length) {
    return <div style={{ color: '#6b7280', textAlign: 'center', padding: 24, fontSize: 13 }}>Entry in progress…</div>;
  }
  const sorted = [...positions].sort((a, b) => {
    const o = { core: 0, hedge: 1 };
    return (o[a.pos_type] ?? 2) - (o[b.pos_type] ?? 2);
  });
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {sorted.map(p => <LegRow key={p.pos_id} pos={p} structureBroken={!structureOk} />)}
    </div>
  );
}
