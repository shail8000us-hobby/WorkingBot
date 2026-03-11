import React, { useState } from 'react'

const PRESET_GRID = {
  desired_ce_premium:   [100, 150, 200],
  desired_pe_premium:   [100, 150, 200],
  initial_lots:         [5, 10],
}

export default function OptimizerPanel() {
  const [mode, setMode]       = useState('grid')
  const [form, setForm]       = useState({ start: '', end: '', underlying: 'BTC', train_days: 20, test_days: 5 })
  const [paramText, setParamText] = useState(JSON.stringify(PRESET_GRID, null, 2))
  const [running, setRunning] = useState(false)
  const [jobId, setJobId]     = useState(null)
  const [jobStatus, setJobStatus] = useState(null)
  const [result, setResult]   = useState(null)
  const [error, setError]     = useState('')

  function set(f) { setForm(p => ({...p, ...f})) }

  async function startJob() {
    setError('')
    let param_grid
    try { param_grid = JSON.parse(paramText) }
    catch(e) { setError('Invalid JSON in param grid'); return }

    if (!form.start || !form.end) { setError('Start and end dates required'); return }

    setRunning(true); setJobId(null); setResult(null); setJobStatus(null)

    const endpoint = { grid: '/api/optimizer/grid', walk_forward: '/api/optimizer/walk_forward' }[mode]
    try {
      const r = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, param_grid }),
      })
      const d = await r.json()
      if (d.success) {
        setJobId(d.job_id)
        pollJob(d.job_id)
      } else { setError(d.error || 'Failed to start'); setRunning(false) }
    } catch(e) { setError(e.message); setRunning(false) }
  }

  async function pollJob(jid) {
    const poll = async () => {
      const r = await fetch(`/api/optimizer/result/${jid}`).catch(() => null)
      if (!r) { setTimeout(poll, 3000); return }
      const d = await r.json()
      setJobStatus(d.status)
      if (d.status === 'done') { setResult(d.result); setRunning(false) }
      else if (d.status === 'error') { setError(d.error || 'Job failed'); setRunning(false) }
      else setTimeout(poll, 3000)
    }
    poll()
  }

  const topResults = result?.results?.slice(0, 10) || result?.windows || []

  return (
    <div>
      <div className="page-header">
        <h2>🔬 Parameter Optimizer</h2>
        <p>Find optimal MMM parameters via grid search or walk-forward optimization</p>
      </div>

      {/* Mode tabs */}
      <div className="tabs" style={{ maxWidth: 360 }}>
        {[['grid','Grid Search'],['walk_forward','Walk-Forward']].map(([k,l]) => (
          <button key={k} className={`tab ${mode===k?'active':''}`} onClick={() => setMode(k)}>{l}</button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        {/* Config */}
        <div className="card">
          <h3 style={{ fontSize: 14, marginBottom: 16 }}>Configuration</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="form-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
              <div className="form-group">
                <label>Start Date</label>
                <input placeholder="DD-MM-YYYY" value={form.start} onChange={e => set({start:e.target.value})} />
              </div>
              <div className="form-group">
                <label>End Date</label>
                <input placeholder="DD-MM-YYYY" value={form.end} onChange={e => set({end:e.target.value})} />
              </div>
              {mode === 'walk_forward' && <>
                <div className="form-group">
                  <label>Train Days</label>
                  <input type="number" value={form.train_days} onChange={e => set({train_days:+e.target.value})} />
                </div>
                <div className="form-group">
                  <label>Test Days</label>
                  <input type="number" value={form.test_days} onChange={e => set({test_days:+e.target.value})} />
                </div>
              </>}
            </div>
          </div>
        </div>

        {/* Param grid */}
        <div className="card">
          <h3 style={{ fontSize: 14, marginBottom: 8 }}>Parameter Grid (JSON)</h3>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
            Each key maps to an array of values to sweep
          </p>
          <textarea
            value={paramText}
            onChange={e => setParamText(e.target.value)}
            style={{ height: 140, fontFamily: 'var(--mono)', fontSize: 12, resize: 'vertical' }}
          />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
        <button className="btn btn-primary" onClick={startJob} disabled={running} style={{ minWidth: 180 }}>
          {running ? <><span className="pulse">⏳</span> Running…</> : `🔬 Start ${mode === 'grid' ? 'Grid Search' : 'Walk-Forward'}`}
        </button>
        {jobId && <span style={{ fontSize: 13, color: 'var(--text-muted)', alignSelf: 'center' }}>Job: <code>{jobId}</code> — {jobStatus || 'starting'}</span>}
        {error && <span style={{ color: 'var(--red)', fontSize: 13, alignSelf: 'center' }}>{error}</span>}
      </div>

      {/* Results */}
      {result && (
        <div className="card fade-in">
          {mode === 'grid' && (
            <>
              <h3 style={{ fontSize: 15, marginBottom: 16 }}>Top Parameter Sets (by Sharpe)</h3>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Params</th>
                    <th>Sharpe</th>
                    <th>Win %</th>
                    <th>Avg P&L</th>
                    <th>Max DD</th>
                  </tr>
                </thead>
                <tbody>
                  {topResults.map((r, i) => (
                    <tr key={i}>
                      <td>#{i+1}</td>
                      <td style={{ fontFamily: 'var(--mono)', fontSize: 11, maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {JSON.stringify(r.params)}
                      </td>
                      <td className="accent">{r.sharpe_ratio?.toFixed(4)}</td>
                      <td>{r.win_rate?.toFixed(1)}%</td>
                      <td className={r.avg_net_pnl >= 0 ? 'green' : 'red'}>${r.avg_net_pnl?.toFixed(0)}</td>
                      <td className="orange">${r.max_drawdown?.toFixed(0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {mode === 'walk_forward' && (
            <>
              <div className="stat-grid" style={{ marginBottom: 20 }}>
                <div className="stat-card">
                  <div className="stat-label">OOS Sharpe</div>
                  <div className="stat-value accent">{result.oos_sharpe?.toFixed(4)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">OOS Win Rate</div>
                  <div className="stat-value green">{result.oos_win_rate?.toFixed(1)}%</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">OOS Avg P&L</div>
                  <div className={`stat-value ${result.oos_avg_pnl >= 0 ? 'green' : 'red'}`}>
                    ${result.oos_avg_pnl?.toFixed(0)}
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">OOS/IS Ratio</div>
                  <div className={`stat-value ${result.efficiency > 0.7 ? 'green' : 'orange'}`}>
                    {result.efficiency?.toFixed(2)}
                    <span style={{ fontSize: 11, marginLeft: 6 }}>{result.efficiency > 0.7 ? '✅' : '⚠️ overfit?'}</span>
                  </div>
                </div>
              </div>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>Windows</h3>
              <table className="data-table">
                <thead><tr><th>#</th><th>Train</th><th>Test</th><th>Best Params</th><th>OOS Sharpe</th><th>OOS Win%</th></tr></thead>
                <tbody>
                  {result.windows?.map((w, i) => (
                    <tr key={i}>
                      <td>{w.window_idx}</td>
                      <td>{w.train_start}→{w.train_end}</td>
                      <td>{w.test_start}→{w.test_end}</td>
                      <td style={{ fontFamily: 'var(--mono)', fontSize: 10 }}>{JSON.stringify(w.best_params)}</td>
                      <td>{w.oos_sharpe_ratio?.toFixed(4)}</td>
                      <td>{w.oos_win_rate?.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  )
}
