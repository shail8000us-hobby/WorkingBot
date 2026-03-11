import React, { useState, useEffect, useRef } from 'react'

const SEVEN_DAYS_AGO = (() => {
  const d = new Date()
  d.setDate(d.getDate() - 6)
  return d.toLocaleDateString('en-GB').split('/').join('-') // DD-MM-YYYY
})()

export default function DataCollector() {
  const [status, setStatus]   = useState(null)
  const [dates, setDates]     = useState({ collected: [], failed: [] })
  const [form, setForm]       = useState({ start: SEVEN_DAYS_AGO, end: '', underlying: 'BTC', overwrite: false })
  const [job, setJob]         = useState(null)   // { job_id, status, message, progress, done, results }
  const pollRef               = useRef(null)

  useEffect(() => { fetchStatus(); fetchDates() }, [])

  async function fetchStatus() {
    try {
      const r = await fetch('/api/data/status')
      const d = await r.json()
      if (d.success) setStatus(d.summary)
    } catch (_) {}
  }

  async function fetchDates() {
    try {
      const r = await fetch('/api/data/dates?underlying=BTC')
      const d = await r.json()
      if (d.success) setDates(d)
    } catch (_) {}
  }

  function startPolling(jobId) {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`/api/data/job/${jobId}`)
        const d = await r.json()
        if (d.success) {
          setJob(d)
          if (d.done) {
            clearInterval(pollRef.current)
            pollRef.current = null
            fetchStatus()
            fetchDates()
          }
        }
      } catch (_) {}
    }, 1500)
  }

  async function startCollection() {
    if (!form.start || !form.end) { alert('Start and end dates required'); return }
    if (pollRef.current) clearInterval(pollRef.current)
    setJob({ status: 'running', message: 'Submitting…', progress: 0, done: false })

    try {
      const r = await fetch('/api/data/collect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const d = await r.json()
      if (d.success) {
        setJob({ status: 'running', message: d.message, progress: 0, done: false, job_id: d.job_id })
        startPolling(d.job_id)
      } else {
        setJob({ status: 'error', message: d.error, done: true })
      }
    } catch (e) {
      setJob({ status: 'error', message: e.message, done: true })
    }
  }

  const collected = dates.collected?.length || 0
  const failed    = dates.failed?.length    || 0

  const statusIcon = () => {
    if (!job) return null
    if (!job.done) return <span className="pulse orange">⏳</span>
    if (job.status === 'done')    return <span className="green">✅</span>
    if (job.status === 'partial') return <span className="orange">⚠️</span>
    return <span className="red">❌</span>
  }

  return (
    <div>
      <div className="page-header">
        <h2>📡 Data Collector</h2>
        <p>Fetch historical options chain + 1-min candles from Delta Exchange India</p>
      </div>

      {/* Important notice */}
      <div style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: 10, padding: '12px 16px', marginBottom: 20, fontSize: 13, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
        <span style={{ fontSize: 18 }}>⚠️</span>
        <div>
          <strong className="orange">7-Day Limit:</strong> Delta Exchange India only provides 1-min candle history for <strong>the last ~7 days</strong>.
          For older data, the engine uses synthetic market data generated from real BTC price distributions.
          <br />
          <span className="muted" style={{ fontSize: 11 }}>Synthetic data: stored at <code>backtesting/historical_data/btc/</code></span>
        </div>
      </div>

      {/* Stats */}
      <div className="stat-grid" style={{ marginBottom: 20 }}>
        <div className="stat-card">
          <div className="stat-label">Collected Dates</div>
          <div className="stat-value accent">{collected}</div>
          <div className="stat-subtext">BTC 0DTE expiries</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Failed</div>
          <div className="stat-value red">{failed}</div>
          <div className="stat-subtext">Too old / no data</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Engine Status</div>
          <div className="stat-value" style={{ fontSize: 16 }}>
            {job && !job.done ? <span className="orange pulse">Collecting…</span> : <span className="green">Ready</span>}
          </div>
        </div>
      </div>

      {/* Collection form */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 15, marginBottom: 6 }}>Collect Real Data from Delta India</h3>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 18 }}>
          Works for dates within the last 6–7 days only (API limitation)
        </p>
        <div className="form-grid" style={{ marginBottom: 16 }}>
          <div className="form-group">
            <label>Start Date</label>
            <input type="text" placeholder="DD-MM-YYYY"
              value={form.start} onChange={e => setForm(f => ({...f, start: e.target.value}))} />
          </div>
          <div className="form-group">
            <label>End Date</label>
            <input type="text" placeholder="DD-MM-YYYY (today)"
              value={form.end} onChange={e => setForm(f => ({...f, end: e.target.value}))} />
          </div>
          <div className="form-group">
            <label>Underlying</label>
            <select value={form.underlying} onChange={e => setForm(f => ({...f, underlying: e.target.value}))}>
              <option value="BTC">BTC</option>
              <option value="ETH">ETH</option>
            </select>
          </div>
          <div className="form-group" style={{ justifyContent: 'flex-end' }}>
            <label>&nbsp;</label>
            <button className="btn btn-primary" onClick={startCollection} disabled={job && !job.done} style={{ width: '100%' }}>
              {job && !job.done ? '⏳ Collecting…' : '📥 Start Collection'}
            </button>
          </div>
        </div>

        {/* Job status card */}
        {job && (
          <div style={{
            padding: '12px 16px',
            background: 'var(--bg-surface)',
            borderRadius: 8,
            borderLeft: `3px solid ${job.status === 'done' ? 'var(--green)' : job.status === 'error' ? 'var(--red)' : 'var(--orange)'}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              {statusIcon()}
              <span style={{ fontSize: 13, fontWeight: 600 }}>{job.message}</span>
            </div>
            {/* Progress bar */}
            {!job.done && (
              <div className="progress-bar" style={{ marginBottom: 8 }}>
                <div className="progress-fill" style={{ width: `${job.progress || 5}%` }} />
              </div>
            )}
            {/* Per-date results */}
            {job.results?.length > 0 && (
              <div style={{ marginTop: 10 }}>
                {job.results.map(r => (
                  <div key={r.date} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0', borderBottom: '1px solid rgba(99,102,241,0.06)' }}>
                    <span style={{ fontFamily: 'var(--mono)' }}>{r.date}</span>
                    {r.success
                      ? <span className="green">✓ {r.rows.toLocaleString()} rows</span>
                      : <span className="red">✗ {r.error}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Collected dates table */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h3 style={{ fontSize: 15 }}>Available Data ({collected})</h3>
          <button className="btn btn-ghost" style={{ padding: '5px 12px', fontSize: 12 }} onClick={() => { fetchStatus(); fetchDates() }}>↻ Refresh</button>
        </div>
        <div style={{ maxHeight: 300, overflowY: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr><th>Date</th><th>Underlying</th><th>Status</th></tr>
            </thead>
            <tbody>
              {dates.collected?.map(d => (
                <tr key={d}><td>{d}</td><td>BTC</td><td><span className="badge green">✓ Ready</span></td></tr>
              ))}
              {dates.failed?.map(d => (
                <tr key={d}><td>{d}</td><td>BTC</td><td><span className="badge red">✗ No API data</span></td></tr>
              ))}
              {collected === 0 && failed === 0 && (
                <tr><td colSpan={3} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>
                  No data yet — click "Start Collection" to fetch recent dates, or run a backtest on <strong>03-03-2026</strong> (synthetic data already available).
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
