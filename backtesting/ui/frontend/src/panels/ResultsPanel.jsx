import React, { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

const fmtUSD = (n) => n == null ? '—' : `${n >= 0 ? '+' : ''}$${Math.abs(n).toLocaleString('en-US', {maximumFractionDigits: 2})}`
const statusColor = (s) => ({ COMPLETE: 'green', STOPPED: 'orange', ERROR: 'red' }[s] || 'muted')

function ProbeCard({ title, data }) {
  return (
    <div className="card" style={{ padding: '14px 18px' }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600, marginBottom: 10 }}>{title}</div>
      {Object.entries(data || {}).map(([k, v]) => (
        <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 5 }}>
          <span style={{ color: 'var(--text-muted)' }}>{k.replace(/_/g, ' ')}</span>
          <span style={{ fontFamily: 'var(--mono)', fontWeight: 500 }}>{typeof v === 'number' ? v.toLocaleString() : String(v)}</span>
        </div>
      ))}
    </div>
  )
}

export default function ResultsPanel() {
  const [history, setHistory]   = useState([])
  const [selected, setSelected] = useState(null)
  const [detail, setDetail]     = useState(null)
  const [probes, setProbes]     = useState(null)
  const [metrics, setMetrics]   = useState(null)
  const [loading, setLoading]   = useState(false)

  useEffect(() => { fetchHistory() }, [])

  async function fetchHistory() {
    const r = await fetch('/api/backtest/history').catch(() => null)
    if (r?.ok) { const d = await r.json(); if (d.success) setHistory(d.results) }
  }

  async function loadResult(id) {
    setLoading(true); setSelected(id); setDetail(null); setProbes(null); setMetrics(null)
    const [r1, r2, r3] = await Promise.all([
      fetch(`/api/backtest/result/${id}`),
      fetch(`/api/analytics/probes/${id}`),
      fetch(`/api/analytics/session/${id}`),
    ])
    const d1 = await r1.json()
    const d2 = await r2.json()
    const d3 = await r3.json()
    if (d1.success) setDetail(d1.result)
    if (d2.success) setProbes(d2.probes)
    if (d3.success) setMetrics(d3.metrics)
    setLoading(false)
  }

  async function deleteResult(id) {
    await fetch(`/api/backtest/result/${id}`, { method: 'DELETE' })
    setHistory(h => h.filter(r => r.result_id !== id))
    if (selected === id) { setSelected(null); setDetail(null) }
  }

  // Mock equity curve from detail fills
  const equityCurve = detail?.fills?.reduce((acc, f) => {
    const prev = acc[acc.length - 1]?.equity ?? 0
    acc.push({ t: acc.length, equity: prev + (f.net_cash_flow || 0) })
    return acc
  }, []) ?? []

  return (
    <div>
      <div className="page-header">
        <h2>📊 Session Results</h2>
        <p>View detailed analytics and weakness probes for each backtest session</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 20 }}>
        {/* Session list */}
        <div className="card" style={{ padding: 0, height: 'fit-content', maxHeight: 600, overflowY: 'auto' }}>
          <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>Sessions ({history.length})</span>
            <button className="btn btn-ghost" style={{ padding: '5px 12px', fontSize: 12 }} onClick={fetchHistory}>↻</button>
          </div>
          {history.length === 0 && (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
              No sessions yet.<br />Run a backtest first.
            </div>
          )}
          {history.map(r => (
            <div key={r.result_id} onClick={() => loadResult(r.result_id)}
              style={{
                padding: '12px 18px', cursor: 'pointer', borderBottom: '1px solid var(--border)',
                background: selected === r.result_id ? 'rgba(99,102,241,0.08)' : 'transparent',
                borderLeft: selected === r.result_id ? '3px solid var(--accent)' : '3px solid transparent',
                transition: 'all 0.15s',
              }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>{r.expiry_date || '?'}</span>
                <span className={`badge ${statusColor(r.strategy_status)}`} style={{ fontSize: 10 }}>
                  {r.strategy_status}
                </span>
              </div>
              <div style={{ fontSize: 12, color: r.net_pnl >= 0 ? 'var(--green)' : 'var(--red)', marginTop: 4, fontFamily: 'var(--mono)' }}>
                {fmtUSD(r.net_pnl)}
              </div>
            </div>
          ))}
        </div>

        {/* Detail panel */}
        <div>
          {loading && <div className="card" style={{ textAlign: 'center', padding: 40 }}>
            <span className="pulse" style={{ fontSize: 24 }}>⏳</span>
            <p style={{ color: 'var(--text-muted)', marginTop: 12 }}>Loading…</p>
          </div>}

          {!loading && !detail && <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
            Select a session on the left to view details
          </div>}

          {!loading && detail && metrics && (
            <>
              {/* P&L stats */}
              <div className="stat-grid" style={{ marginBottom: 16 }}>
                {[
                  ['Net P&L',     fmtUSD(metrics.net_pnl),     metrics.net_pnl >= 0 ? 'green' : 'red'],
                  ['Total P&L',   fmtUSD(metrics.total_pnl),   'accent'],
                  ['Sharpe',      'N/A (single)',               'muted'],
                  ['Max DD',      fmtUSD(metrics.max_drawdown), 'orange'],
                  ['Calmar',      metrics.calmar_ratio,         'accent'],
                  ['Adjustments', metrics.adjustment_count,     ''],
                  ['Fees',        fmtUSD(-metrics.total_fees),  'red'],
                  ['Slippage',    fmtUSD(-metrics.total_slippage_usd), 'red'],
                ].map(([l, v, c]) => (
                  <div className="stat-card" key={l}>
                    <div className="stat-label">{l}</div>
                    <div className={`stat-value ${c}`} style={{ fontSize: 16 }}>{String(v)}</div>
                  </div>
                ))}
              </div>

              {/* Equity curve */}
              {equityCurve.length > 1 && (
                <div className="chart-wrapper">
                  <div className="chart-title">Realized P&L Curve</div>
                  <ResponsiveContainer width="100%" height={180}>
                    <LineChart data={equityCurve}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.1)" />
                      <XAxis dataKey="t" hide />
                      <YAxis tickFormatter={v => `$${v.toFixed(0)}`} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                      <Tooltip formatter={v => fmtUSD(v)} contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }} />
                      <Line type="monotone" dataKey="equity" stroke="var(--accent)" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Weakness probes */}
              {probes && (
                <div>
                  <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--text-muted)' }}>WEAKNESS PROBES</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
                    {Object.entries(probes).map(([k, v]) => <ProbeCard key={k} title={k.replace(/_/g, ' ')} data={v} />)}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
