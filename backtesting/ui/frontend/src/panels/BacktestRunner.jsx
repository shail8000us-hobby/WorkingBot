import React, { useState } from 'react'

const DEFAULT_PARAMS = {
  desired_ce_premium:   150,
  desired_pe_premium:   150,
  initial_lots:         10,
  min_trigger_move_pct: 3.0,
  close_at_threshold:   5.0,
  wind_down_enabled:    true,
  wind_down_minutes:    120,
  harvest_enabled:      true,
  recycle_enabled:      true,
}

const fmtUSD = (n) => n == null ? '—' : `${n >= 0 ? '+' : ''}$${Math.abs(n).toLocaleString('en-US', {maximumFractionDigits: 2})}`
const statusColor = (s) => ({ COMPLETE: 'green', STOPPED: 'orange', ERROR: 'red' }[s] || 'accent')

export default function BacktestRunner() {
  const [form, setForm] = useState({
    expiry_date: '', underlying: 'BTC', mode: 'fresh',
    entry_time: '09:15', slippage_bps: 2, initial_margin_usd: 500000,
  })
  const [params, setParams]     = useState(DEFAULT_PARAMS)
  const [running, setRunning]   = useState(false)
  const [result, setResult]     = useState(null)
  const [error, setError]       = useState('')

  function set(f) { setForm(p => ({...p, ...f})) }
  function setP(f) { setParams(p => ({...p, ...f})) }

  async function run() {
    if (!form.expiry_date) { setError('Expiry date required'); return }
    setRunning(true); setError(''); setResult(null)
    try {
      const r = await fetch('/api/backtest/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, params }),
      })
      const d = await r.json()
      if (d.success) setResult({ ...d.summary, result_id: d.result_id })
      else setError(d.error || 'Unknown error')
    } catch(e) { setError(e.message) }
    setRunning(false)
  }

  return (
    <div>
      <div className="page-header">
        <h2>▶️ Run Backtest</h2>
        <p>Configure and run a single MMM backtest session on historical data</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
        {/* Session config */}
        <div className="card">
          <h3 style={{ fontSize: 15, marginBottom: 20 }}>Session Config</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="form-group">
              <label>Expiry Date</label>
              <input placeholder="DD-MM-YYYY e.g. 08-03-2026" value={form.expiry_date}
                onChange={e => set({ expiry_date: e.target.value })} />
            </div>
            <div className="form-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
              <div className="form-group">
                <label>Underlying</label>
                <select value={form.underlying} onChange={e => set({ underlying: e.target.value })}>
                  <option value="BTC">BTC</option>
                  <option value="ETH">ETH</option>
                </select>
              </div>
              <div className="form-group">
                <label>Mode</label>
                <select value={form.mode} onChange={e => set({ mode: e.target.value })}>
                  <option value="fresh">Fresh (scan chain)</option>
                  <option value="import">Import (specific strikes)</option>
                </select>
              </div>
              <div className="form-group">
                <label>Entry Time (IST)</label>
                <input type="text" placeholder="09:15" value={form.entry_time}
                  onChange={e => set({ entry_time: e.target.value })} />
              </div>
              <div className="form-group">
                <label>Slippage (bps)</label>
                <input type="number" value={form.slippage_bps}
                  onChange={e => set({ slippage_bps: +e.target.value })} />
              </div>
            </div>
          </div>
        </div>

        {/* MMM params */}
        <div className="card">
          <h3 style={{ fontSize: 15, marginBottom: 20 }}>MMM Parameters</h3>
          <div className="form-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
            {[
              ['desired_ce_premium', 'CE Target Premium ($)'],
              ['desired_pe_premium', 'PE Target Premium ($)'],
              ['initial_lots', 'Initial Lots'],
              ['min_trigger_move_pct', 'Trigger Move %'],
              ['close_at_threshold', 'Close-at-5 Threshold'],
              ['wind_down_minutes', 'Wind-down (mins)'],
            ].map(([key, lbl]) => (
              <div className="form-group" key={key}>
                <label>{lbl}</label>
                <input type="number" value={params[key]}
                  onChange={e => setP({ [key]: +e.target.value })} />
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 14, flexWrap: 'wrap' }}>
            {[['harvest_enabled', '🌾 Harvest'], ['recycle_enabled', '♻️ Recycle'], ['wind_down_enabled', '💨 Wind-down']].map(([key, lbl]) => (
              <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', userSelect: 'none' }}>
                <input type="checkbox" checked={params[key]}
                  onChange={e => setP({ [key]: e.target.checked })}
                  style={{ width: 'auto', marginBottom: 0 }} />
                <span style={{ fontSize: 13 }}>{lbl}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* Run button */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
        <button className="btn btn-primary" onClick={run} disabled={running} style={{ minWidth: 160 }}>
          {running ? <><span className="pulse">⏳</span> Running…</> : '▶️ Run Backtest'}
        </button>
        {error && <span style={{ color: 'var(--red)', fontSize: 13, display: 'flex', alignItems: 'center' }}>{error}</span>}
      </div>

      {/* Result */}
      {result && (
        <div className="card fade-in">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <h3 style={{ fontSize: 15 }}>Session Result — {result.expiry_date}</h3>
            <span className={`badge ${statusColor(result.strategy_status)}`}>{result.strategy_status}</span>
          </div>

          <div className="stat-grid">
            {[
              ['Net P&L', fmtUSD(result.net_pnl), '', result.net_pnl >= 0 ? 'green' : 'red'],
              ['Adjustments', result.adjustment_count, '', 'accent'],
              ['Max Drawdown', fmtUSD(result.max_drawdown), '', 'orange'],
              ['Fees', fmtUSD(-result.total_fees), '', 'red'],
              ['Duration', `${result.duration_hours?.toFixed(1) ?? '?'}h`, '', 'accent'],
              ['Fills', result.total_fills, '', ''],
            ].map(([label, val, sub, cls]) => (
              <div className="stat-card" key={label}>
                <div className="stat-label">{label}</div>
                <div className={`stat-value ${cls}`} style={{ fontSize: 18 }}>{val}</div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 12, padding: '10px 14px', background: 'var(--bg-surface)', borderRadius: 8 }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Result ID: </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{result.result_id}</span>
          </div>
        </div>
      )}
    </div>
  )
}
