/**
 * SSDHStatusBanner — Session header: status + running-since elapsed + net P&L + trailing stop bar
 *
 * No countdown — SSDH runs to expiry or until operator exits. It is a 2× hedged
 * strategy with minimal theta decay, so time-based auto-exit is not applicable.
 */
import React, { useEffect, useState } from 'react';

const STATUS_COLOR = { RUNNING:'#10b981', INITIALIZING:'#f59e0b', WIND_DOWN:'#f97316', CLOSED:'#6b7280', ABORTED:'#ef4444', EMERGENCY:'#ef4444', IDLE:'#6b7280' };

function fmtElapsed(sec) {
  if (!sec || sec < 0) return '—';
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.floor(sec % 60);
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`;
  return `${m}m ${String(s).padStart(2, '0')}s`;
}

function fmtPnl(v) {
  if (v == null) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(4)} BTC`;
}

export default function SSDHStatusBanner({ session, vegaSpike, structureOk }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const startedAt = session?.started_at;
    if (!startedAt) { setElapsed(0); return; }
    const tick = () => setElapsed(Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [session?.started_at]);

  if (!session) return null;

  const status = session.status || 'IDLE';
  const sc     = STATUS_COLOR[status] || '#6b7280';
  const net    = session.net_pnl ?? 0;
  const peak   = session.peak_net_pnl ?? 0;
  const trail  = (session.params?.trailing_stop_pct ?? 0.5);
  const floor  = peak > 0 ? peak * (1 - trail) : null;

  // progress = how far current P&L is from floor toward peak (0–100%)
  const progress = peak > 0 ? Math.min(100, Math.max(0, ((net - (floor ?? 0)) / (peak - (floor ?? 0))) * 100)) : 0;
  const barColor = progress > 70 ? '#22c55e' : progress > 30 ? '#f59e0b' : '#ef4444';

  return (
    <div>
      {/* Structure break */}
      {!structureOk && (
        <div style={{ background: '#7f1d1d', color: '#fca5a5', padding: '8px 16px', fontWeight: 700, fontSize: 14, textAlign: 'center', borderRadius: '8px 8px 0 0', letterSpacing: 1 }}>
          ⚠ STRUCTURE BROKEN — EMERGENCY EXIT IN PROGRESS
        </div>
      )}
      {/* Vega spike */}
      {vegaSpike && (
        <div style={{ background: '#78350f', color: '#fde68a', padding: '6px 16px', fontSize: 13, textAlign: 'center' }}>
          ⚠ Vega spike detected — short legs expanded without directional move
        </div>
      )}
      {/* Main bar */}
      <div style={{ background: '#1f2937', borderRadius: (!structureOk || vegaSpike) ? '0 0 8px 8px' : 8, padding: '12px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
          <span style={{ background: sc, color: '#fff', padding: '3px 10px', borderRadius: 4, fontWeight: 700, fontSize: 11, letterSpacing: 1 }}>{status}</span>
          <span style={{ color: '#6b7280', fontSize: 12, fontFamily: 'monospace' }}>{session.session_id}</span>
          {session.started_at && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span style={{ fontSize: 9, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.5 }}>Running For</span>
              <span style={{ fontSize: 20, fontFamily: 'monospace', fontWeight: 700, color: '#f9fafb' }}>{fmtElapsed(elapsed)}</span>
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <span style={{ fontSize: 9, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.5 }}>Net P&amp;L</span>
            <span style={{ fontSize: 18, fontFamily: 'monospace', fontWeight: 700, color: net >= 0 ? '#22c55e' : '#ef4444' }}>{fmtPnl(net)}</span>
          </div>
          {peak > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span style={{ fontSize: 9, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.5 }}>Peak</span>
              <span style={{ fontSize: 14, fontFamily: 'monospace', color: '#60a5fa' }}>{fmtPnl(peak)}</span>
            </div>
          )}
          {floor !== null && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span style={{ fontSize: 9, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.5 }}>Stop Floor</span>
              <span style={{ fontSize: 14, fontFamily: 'monospace', color: '#f97316' }}>{fmtPnl(floor)}</span>
            </div>
          )}
        </div>
        {/* Trailing stop P&L progress bar */}
        {peak > 0 && (
          <div style={{ marginTop: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#6b7280', marginBottom: 3 }}>
              <span>Stop floor {fmtPnl(floor)}</span>
              <span>{Math.round(progress)}% to stop trigger</span>
              <span>Peak {fmtPnl(peak)}</span>
            </div>
            <div style={{ background: '#374151', borderRadius: 3, height: 6, overflow: 'hidden' }}>
              <div style={{ width: `${progress}%`, background: barColor, height: '100%', borderRadius: 3, transition: 'width 1s' }} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
