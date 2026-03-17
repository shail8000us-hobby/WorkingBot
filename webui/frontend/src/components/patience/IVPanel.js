/**
 * IVPanel — DVOL percentile chart and current IV display.
 * Polls /api/patience/iv/current every 15 minutes.
 *
 * Created: March 14, 2026
 */

import React, { useState, useEffect } from 'react';
import patienceAPI from './patienceService';

export default function IVPanel() {
  const [current, setCurrent] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [armedCards, setArmedCards] = useState([]);

  useEffect(() => {
    const fetch = async () => {
      try {
        const [c, h, cardsRes] = await Promise.all([
          patienceAPI.getIVCurrent(),
          patienceAPI.getIVHistory(30),
          patienceAPI.getCards(),
        ]);
        setCurrent(c.data);
        setHistory((h.data?.history || []).slice(0, 120).reverse());
        const all = cardsRes.data?.cards || [];
        setArmedCards(all.filter(c => ['ARMED', 'WAITING'].includes(c.status) && (c.iv_percentile_min || c.iv_percentile_max)));
      } catch (e) { /* silent */ }
      finally { setLoading(false); }
    };
    fetch();
    const id = setInterval(fetch, 15 * 60 * 1000); // 15 min
    return () => clearInterval(id);
  }, []);

  const pct = current?.percentile;
  const dvol = current?.dvol;
  const pctColor = pct === null ? '#64748b' : pct < 25 ? '#22c55e' : pct < 50 ? '#eab308' : pct < 75 ? '#f97316' : '#ef4444';

  // Simple bar chart
  const chartHeight = 120;
  const values = history.map(h => h.dvol_value).filter(v => v != null);
  const minV = values.length ? Math.min(...values) : 0;
  const maxV = values.length ? Math.max(...values) : 100;
  const range = maxV - minV || 1;

  return (
    <div style={{ color: '#e2e8f0' }}>
      <h4 style={{ color: '#a78bfa', marginTop: 0 }}>Deribit DVOL — BTC Implied Volatility Index</h4>

      {loading ? (
        <div style={{ color: '#64748b' }}>Loading IV data...</div>
      ) : (
        <>
          {current?.note && (
            <div style={{ color: '#64748b', fontSize: 12, marginBottom: 12 }}>{current.note}</div>
          )}

          {/* Current value */}
          <div style={{ display: 'flex', gap: 24, marginBottom: 20 }}>
            <div style={{ background: '#0f172a', borderRadius: 8, padding: 16, textAlign: 'center', minWidth: 120 }}>
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>DVOL (Current)</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#e2e8f0' }}>{dvol?.toFixed(1) ?? '—'}</div>
            </div>
            <div style={{ background: '#0f172a', borderRadius: 8, padding: 16, textAlign: 'center', minWidth: 120 }}>
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Percentile (30d)</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: pctColor }}>{pct?.toFixed(1) ?? '—'}%</div>
            </div>
            <div style={{ background: '#0f172a', borderRadius: 8, padding: 16, flex: 1 }}>
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8 }}>Position in Distribution</div>
              <div style={{ background: '#1e293b', borderRadius: 4, height: 12, position: 'relative' }}>
                {pct !== null && (
                  <>
                    <div style={{ position: 'absolute', left: `${pct}%`, top: -4, width: 3, height: 20, background: pctColor, borderRadius: 2 }} />
                    <div style={{ position: 'absolute', left: 0, width: `${pct}%`, height: '100%', background: pctColor, opacity: 0.3, borderRadius: 4 }} />
                  </>
                )}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#64748b', marginTop: 4 }}>
                <span>0% (cheap)</span><span>50%</span><span>100% (expensive)</span>
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 8 }}>
                {pct < 25 ? '🟢 IV cheap — good for debit spreads' :
                 pct < 50 ? '🟡 IV moderate' :
                 pct < 75 ? '🟠 IV elevated — good for credit spreads' :
                 pct !== null ? '🔴 IV expensive — strong credit opportunity' : '—'}
              </div>
            </div>
          </div>

          {/* ── IV Gate Status for armed cards ── */}
          {armedCards.length > 0 && (
            <div style={{ background: '#0f172a', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 10 }}>IV Gate Status — Armed Cards</div>
              {armedCards.map(card => {
                const min = card.iv_percentile_min;
                const max = card.iv_percentile_max;
                const passes = (min == null || pct >= min) && (max == null || pct <= max);
                const gateLabel = [
                  min != null ? `≥${min}%` : null,
                  max != null ? `≤${max}%` : null,
                ].filter(Boolean).join(' & ');
                return (
                  <div key={card.card_id} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700,
                      background: pct == null ? '#334155' : passes ? '#166534' : '#7f1d1d',
                      color: pct == null ? '#64748b' : passes ? '#22c55e' : '#ef4444',
                    }}>
                      {pct == null ? 'N/A' : passes ? '✓ PASS' : '✗ BLOCK'}
                    </span>
                    <span style={{ fontSize: 13, color: '#e2e8f0' }}>{card.card_name}</span>
                    <span style={{ fontSize: 11, color: '#64748b' }}>IV {gateLabel}</span>
                    <span style={{ fontSize: 11, color: '#475569' }}>
                      (current: {pct != null ? `${pct.toFixed(1)}%` : '—'})
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Simple bar chart */}
          {values.length > 1 && (
            <div style={{ background: '#0f172a', borderRadius: 8, padding: 16 }}>
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 10 }}>30-Day DVOL History</div>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1, height: chartHeight }}>
                {history.slice(-60).map((h, i) => {
                  const v = h.dvol_value;
                  const barH = v != null ? ((v - minV) / range) * chartHeight : 0;
                  const isCurrentDay = i === history.slice(-60).length - 1;
                  return (
                    <div
                      key={i}
                      title={`${h.timestamp?.slice(0, 10)}: ${v?.toFixed(1)}`}
                      style={{
                        flex: 1,
                        height: barH,
                        background: isCurrentDay ? '#a78bfa' : '#3b82f6',
                        opacity: isCurrentDay ? 1 : 0.6,
                        borderRadius: '2px 2px 0 0',
                        minHeight: 2,
                        cursor: 'default',
                      }}
                    />
                  );
                })}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#475569', marginTop: 4 }}>
                <span>30 days ago</span>
                <span>Today</span>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
