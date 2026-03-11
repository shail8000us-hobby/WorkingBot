import React, { useState } from 'react'
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts'

const fmtUSD = (n) => n == null ? '—' : `${n >= 0 ? '+' : ''}$${Math.abs(n).toLocaleString('en-US', {maximumFractionDigits: 2})}`

const METRICS = ['sharpe_ratio','win_rate','avg_net_pnl','max_drawdown','avg_adjustments','total_net_pnl']

export default function ComparisonPanel() {
  const [setA, setSetA]       = useState('')
  const [setB, setSetB]       = useState('')
  const [labelA, setLabelA]   = useState('Config A')
  const [labelB, setLabelB]   = useState('Config B')
  const [result, setResult]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  async function compare() {
    if (!setA.trim() || !setB.trim()) { setError('Both sets require result IDs'); return }
    setLoading(true); setError(''); setResult(null)
    const url = `/api/analytics/compare?set_a=${encodeURIComponent(setA.trim())}&set_b=${encodeURIComponent(setB.trim())}&label_a=${encodeURIComponent(labelA)}&label_b=${encodeURIComponent(labelB)}`
    const r = await fetch(url).catch(() => null)
    const d = await r?.json()
    if (d?.success) setResult(d.comparison)
    else setError(d?.error || 'Compare failed')
    setLoading(false)
  }

  // Build bar chart data
  const barData = result ? METRICS.map(m => ({
    metric: m.replace(/_/g, ' '),
    [labelA]: result[labelA]?.portfolio?.[m] ?? 0,
    [labelB]: result[labelB]?.portfolio?.[m] ?? 0,
  })) : []

  // Build radar chart data
  const radarData = result ? ['win_rate','sharpe_ratio','sortino_ratio'].map(m => ({
    metric: m.replace(/_/g, ' '),
    [labelA]: Math.abs(result[labelA]?.portfolio?.[m] ?? 0),
    [labelB]: Math.abs(result[labelB]?.portfolio?.[m] ?? 0),
  })) : []

  function CompareRow({ label, valA, valB, fmt: f = String, higherIsBetter = true }) {
    const a = typeof valA === 'number' ? valA : 0
    const b = typeof valB === 'number' ? valB : 0
    const aWins = higherIsBetter ? a > b : a < b
    const bWins = higherIsBetter ? b > a : b < a
    return (
      <tr>
        <td style={{ color: 'var(--text-muted)', fontSize: 12, paddingLeft: 0 }}>{label}</td>
        <td style={{ fontFamily: 'var(--mono)', fontSize: 13, color: aWins ? 'var(--green)' : 'inherit' }}>
          {typeof valA === 'number' ? f(valA) : '—'} {aWins && '✓'}
        </td>
        <td style={{ fontFamily: 'var(--mono)', fontSize: 13, color: bWins ? 'var(--green)' : 'inherit' }}>
          {typeof valB === 'number' ? f(valB) : '—'} {bWins && '✓'}
        </td>
      </tr>
    )
  }

  return (
    <div>
      <div className="page-header">
        <h2>⚖️ A/B Comparison</h2>
        <p>Compare two sets of backtest results side-by-side (different params, date ranges, etc.)</p>
      </div>

      {/* Input */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: 14, marginBottom: 16 }}>Configure Comparison</h3>
        <div className="form-grid" style={{ marginBottom: 16 }}>
          <div className="form-group">
            <label>Label A</label>
            <input value={labelA} onChange={e => setLabelA(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Set A — Result IDs (comma-separated)</label>
            <input placeholder="e.g. abc123, def456" value={setA} onChange={e => setSetA(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Label B</label>
            <input value={labelB} onChange={e => setLabelB(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Set B — Result IDs (comma-separated)</label>
            <input placeholder="e.g. ghi789, jkl012" value={setB} onChange={e => setSetB(e.target.value)} />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button className="btn btn-primary" onClick={compare} disabled={loading}>
            {loading ? '⏳ Comparing…' : '⚖️ Compare'}
          </button>
          {error && <span style={{ color: 'var(--red)', fontSize: 13 }}>{error}</span>}
        </div>
      </div>

      {result && (
        <div className="fade-in">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
            {/* Comparison Table */}
            <div className="card">
              <h3 style={{ fontSize: 14, marginBottom: 16 }}>Side-by-Side Metrics</h3>
              <table className="data-table">
                <thead><tr><th>Metric</th><th>{labelA}</th><th>{labelB}</th></tr></thead>
                <tbody>
                  <CompareRow label="Win Rate %"    valA={result[labelA]?.portfolio?.win_rate}     valB={result[labelB]?.portfolio?.win_rate}     fmt={v => `${v.toFixed(1)}%`} />
                  <CompareRow label="Sharpe Ratio"  valA={result[labelA]?.portfolio?.sharpe_ratio}  valB={result[labelB]?.portfolio?.sharpe_ratio}  fmt={v => v.toFixed(4)} />
                  <CompareRow label="Sortino"       valA={result[labelA]?.portfolio?.sortino_ratio} valB={result[labelB]?.portfolio?.sortino_ratio} fmt={v => v.toFixed(4)} />
                  <CompareRow label="Avg Net P&L"   valA={result[labelA]?.portfolio?.avg_net_pnl}   valB={result[labelB]?.portfolio?.avg_net_pnl}   fmt={fmtUSD} />
                  <CompareRow label="Total Net P&L" valA={result[labelA]?.portfolio?.total_net_pnl} valB={result[labelB]?.portfolio?.total_net_pnl} fmt={fmtUSD} />
                  <CompareRow label="Max Drawdown"  valA={result[labelA]?.portfolio?.max_drawdown}  valB={result[labelB]?.portfolio?.max_drawdown}  fmt={fmtUSD} higherIsBetter={false} />
                  <CompareRow label="Avg Adj/Session" valA={result[labelA]?.portfolio?.avg_adjustments} valB={result[labelB]?.portfolio?.avg_adjustments} higherIsBetter={false} />
                  <CompareRow label="Total Fees"    valA={result[labelA]?.portfolio?.total_fees}    valB={result[labelB]?.portfolio?.total_fees}    fmt={v => fmtUSD(-v)} higherIsBetter={false} />
                </tbody>
              </table>
            </div>

            {/* Radar chart */}
            <div className="chart-wrapper">
              <div className="chart-title">Risk-Return Profile</div>
              {radarData.length > 0 && (
                <ResponsiveContainer width="100%" height={200}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="rgba(99,102,241,0.15)" />
                    <PolarAngleAxis dataKey="metric" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <Radar name={labelA} dataKey={labelA} stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.2} />
                    <Radar name={labelB} dataKey={labelB} stroke="var(--accent2)" fill="var(--accent2)" fillOpacity={0.2} />
                    <Legend />
                  </RadarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Bar chart */}
          <div className="chart-wrapper">
            <div className="chart-title">Portfolio Metrics Comparison</div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={barData.filter(d => d.metric !== 'max drawdown')}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.1)" />
                <XAxis dataKey="metric" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }} />
                <Legend />
                <Bar dataKey={labelA} fill="var(--accent)" radius={[4,4,0,0]} />
                <Bar dataKey={labelB} fill="var(--accent2)" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {!result && !loading && (
        <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
          Enter result IDs for both sets and click Compare.<br />
          <span style={{ fontSize: 12, marginTop: 8, display: 'block' }}>You can find result IDs in the Results panel.</span>
        </div>
      )}
    </div>
  )
}
