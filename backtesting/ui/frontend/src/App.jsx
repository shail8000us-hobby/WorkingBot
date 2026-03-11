import React, { useState } from 'react'
import DataCollector from './panels/DataCollector'
import BacktestRunner from './panels/BacktestRunner'
import ResultsPanel  from './panels/ResultsPanel'
import OptimizerPanel from './panels/OptimizerPanel'
import ComparisonPanel from './panels/ComparisonPanel'

const NAV = [
  { id: 'data',       label: '📡 Data Collector',   desc: 'Collect historical data'     },
  { id: 'backtest',   label: '▶️  Run Backtest',      desc: 'Run MMM sessions'            },
  { id: 'results',    label: '📊 Results',            desc: 'View session results'        },
  { id: 'optimizer',  label: '🔬 Optimizer',          desc: 'Parameter optimization'     },
  { id: 'comparison', label: '⚖️  Compare',            desc: 'A/B comparison'             },
]

export default function App() {
  const [active, setActive] = useState('backtest')

  const panel = () => {
    switch (active) {
      case 'data':       return <DataCollector />
      case 'backtest':   return <BacktestRunner />
      case 'results':    return <ResultsPanel />
      case 'optimizer':  return <OptimizerPanel />
      case 'comparison': return <ComparisonPanel />
      default:           return <BacktestRunner />
    }
  }

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>BackTest</h1>
          <span>MMM Engine · port 5557</span>
        </div>

        <div className="nav-section">Navigation</div>

        {NAV.map(n => (
          <button
            key={n.id}
            className={`nav-item ${active === n.id ? 'active' : ''}`}
            onClick={() => setActive(n.id)}
          >
            {n.label}
          </button>
        ))}

        <div style={{ marginTop: 'auto', padding: '20px', borderTop: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            <span style={{ color: 'var(--green)', marginRight: 6 }}>●</span>
            Independent module · No live trading
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="main-content fade-in" key={active}>
        {panel()}
      </main>
    </div>
  )
}
