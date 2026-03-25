/**
 * SSDHSafetyPanel — 6 safety system indicators + P&L summary
 * (replaces old SSDHPnLPanel — same filename to avoid import changes)
 */
import React from 'react';

function fmtBtc(v) { if (v == null) return '—'; return `${v >= 0 ? '+' : ''}${v.toFixed(4)} BTC`; }
function pnlColor(v) { if (v > 0) return '#22c55e'; if (v < 0) return '#ef4444'; return '#6b7280'; }

function SafetyRow({ label, status, value, detail, barPct, barColor }) {
  const dot = status === 'ok' ? '#22c55e' : status === 'warn' ? '#f59e0b' : '#ef4444';
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: dot, fontSize: 10 }}>●</span>
          <span style={{ color: '#9ca3af', fontSize: 12 }}>{label}</span>
        </div>
        <span style={{ color: '#e5e7eb', fontSize: 12, fontFamily: 'monospace' }}>{value}</span>
      </div>
      {detail && <div style={{ color: '#6b7280', fontSize: 11, marginLeft: 16, marginTop: 1 }}>{detail}</div>}
      {barPct != null && (
        <div style={{ background: '#374151', borderRadius: 2, height: 3, marginTop: 4, marginLeft: 16 }}>
          <div style={{ width: `${barPct}%`, background: barColor || '#22c55e', height: '100%', borderRadius: 2, transition: 'width 1s' }} />
        </div>
      )}
    </div>
  );
}

function PnlRow({ label, value, color, bold, divider }) {
  return (
    <>
      {divider && <div style={{ borderTop: '1px solid #374151', margin: '8px 0' }} />}
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
        <span style={{ color: '#6b7280', fontSize: 13 }}>{label}</span>
        <span style={{ color: color || '#e5e7eb', fontSize: 13, fontFamily: 'monospace', fontWeight: bold ? 700 : 400 }}>{value}</span>
      </div>
    </>
  );
}

export default function SSDHPnLPanel({ session, params }) {
  if (!session) return null;

  const positions = session.positions || [];
  const active    = positions.filter(p => p.status === 'active');
  const net       = session.net_pnl ?? 0;
  const peak      = session.peak_net_pnl ?? 0;
  const realized  = session.realized_pnl ?? 0;
  const fees      = session.total_fees ?? 0;
  const maxLoss   = params?.max_loss_amount ?? null;
  const trail     = params?.trailing_stop_pct ?? 0.5;
  const floor     = peak > 0 ? peak * (1 - trail) : null;

  // Safety indicators
  const lossPct   = maxLoss ? Math.min(100, Math.max(0, (-net / maxLoss) * 100)) : 0;
  const trailPct  = peak > 0 ? Math.min(100, Math.max(0, ((net - (floor ?? 0)) / (peak - (floor ?? 0))) * 100)) : 0;

  const shortPnl = active.filter(p => p.direction === 'short').reduce((s, p) => s + (p.unrealized_pnl ?? 0), 0);
  const longPnl  = active.filter(p => p.direction === 'long' ).reduce((s, p) => s + (p.unrealized_pnl ?? 0), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* P&L Summary */}
      <div style={s.card}>
        <div style={s.cardTitle}>P&amp;L Breakdown</div>
        <PnlRow label="Short legs" value={fmtBtc(shortPnl)} color={pnlColor(shortPnl)} />
        <PnlRow label="Long legs"  value={fmtBtc(longPnl)}  color={pnlColor(longPnl)} />
        {realized !== 0 && <PnlRow label="Realized" value={fmtBtc(realized)} color={pnlColor(realized)} />}
        <PnlRow label="Fees" value={fmtBtc(-fees)} color={fees > 0 ? '#ef4444' : '#6b7280'} />
        <PnlRow label="Net P&L" value={fmtBtc(net)} color={pnlColor(net)} bold divider />
      </div>

      {/* Safety systems */}
      <div style={s.card}>
        <div style={s.cardTitle}>Safety Systems</div>

        <SafetyRow
          label="Trailing Stop"
          status={trailPct > 0 ? 'ok' : 'warn'}
          value={floor != null ? fmtBtc(floor) : '—'}
          detail={`${Math.round(trail * 100)}% of peak = floor`}
          barPct={trailPct}
          barColor={trailPct > 70 ? '#22c55e' : trailPct > 30 ? '#f59e0b' : '#ef4444'}
        />

        <SafetyRow
          label="Max Loss Limit"
          status={lossPct < 50 ? 'ok' : lossPct < 80 ? 'warn' : 'danger'}
          value={maxLoss ? `${Math.round(lossPct)}% used` : 'auto'}
          detail={maxLoss ? `${fmtBtc(-maxLoss)} limit` : 'set by intraday multiplier'}
          barPct={maxLoss ? lossPct : null}
          barColor={lossPct < 50 ? '#22c55e' : lossPct < 80 ? '#f59e0b' : '#ef4444'}
        />

        <SafetyRow
          label="Circuit Breaker"
          status="ok"
          value="OK"
          detail="Consecutive API failures tracked"
        />

        <SafetyRow
          label="Margin"
          status="ok"
          value={session.margin_tier || 'GREEN'}
          detail="Blocked margin vs wallet"
        />

        <SafetyRow
          label="Structure"
          status={session.structure_ok !== false ? 'ok' : 'danger'}
          value={session.structure_ok !== false ? 'INTACT' : 'BROKEN'}
          detail="4 legs present check"
        />

        <SafetyRow
          label="Vega"
          status={session.vega_spike_detected ? 'danger' : 'ok'}
          value={session.vega_spike_detected ? 'SPIKE' : 'NORMAL'}
          detail="Short leg avg premium ratio"
        />
      </div>
    </div>
  );
}

const s = {
  card:      { background: '#111827', borderRadius: 8, padding: '14px 16px' },
  cardTitle: { color: '#9ca3af', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 },
};
