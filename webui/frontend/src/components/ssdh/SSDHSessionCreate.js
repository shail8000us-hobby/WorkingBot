/**
 * SSDHSessionCreate — 3-phase session creation wizard
 *
 * Phase 1 (configure): lots, session window, trailing stop, max loss
 * Phase 2 (chain):     expiry picker + live option chain + structure builder + payoff graph
 * Phase 3 (confirm):   review legs + financials + execute
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';

const LOT_SIZE = 0.001;
const LEG_SEQUENCE = ['short_ce', 'short_pe', 'long_ce', 'long_pe'];
const LEG_LABELS = {
  short_ce: 'SHORT CE',
  short_pe: 'SHORT PE',
  long_ce:  'LONG CE HEDGE',
  long_pe:  'LONG PE HEDGE',
};
const LEG_COLORS = {
  short_ce: { border: '#dc2626', bg: '#450a0a', text: '#fca5a5' },
  short_pe: { border: '#dc2626', bg: '#450a0a', text: '#fca5a5' },
  long_ce:  { border: '#16a34a', bg: '#052e16', text: '#86efac' },
  long_pe:  { border: '#16a34a', bg: '#052e16', text: '#86efac' },
};

// ─── Payoff graph ─────────────────────────────────────────────────────────────

function computePayoff(legs, spot) {
  const N = 100;
  const min = spot * 0.85, max = spot * 1.15;
  return Array.from({ length: N }, (_, i) => {
    const s = min + (max - min) * i / (N - 1);
    let pnl = 0;
    LEG_SEQUENCE.forEach(key => {
      const leg = legs[key];
      if (!leg) return;
      const intrinsic = leg.side === 'CE'
        ? Math.max(0, s - leg.strike)
        : Math.max(0, leg.strike - s);
      pnl += leg.direction === 'short'
        ? (leg.target_premium - intrinsic) * leg.lots * LOT_SIZE
        : (-leg.target_premium + intrinsic) * leg.lots * LOT_SIZE;
    });
    return { s, pnl };
  });
}

function PayoffGraph({ legs, spot }) {
  const allFilled = LEG_SEQUENCE.every(k => legs[k]);
  const filledCount = LEG_SEQUENCE.filter(k => legs[k]).length;
  if (filledCount < 2) return null;

  const data = computePayoff(legs, spot);
  const pnls = data.map(d => d.pnl);
  const minPnl = Math.min(...pnls, 0);
  const maxPnl = Math.max(...pnls, 0);
  const range = maxPnl - minPnl || 0.001;

  const W = 500, H = 160, PL = 42, PR = 10, PT = 18, PB = 28;
  const iW = W - PL - PR, iH = H - PT - PB;

  const tx = i => PL + (i / (data.length - 1)) * iW;
  const ty = v => PT + iH - ((v - minPnl) / range) * iH;
  const zeroY = ty(0);
  const spotX = PL + ((spot - spot * 0.85) / (spot * 0.30)) * iW;

  const pts = data.map((d, i) => `${tx(i)},${ty(d.pnl)}`).join(' ');
  const abovePts = `${PL},${zeroY} ${data.map((d, i) => `${tx(i)},${ty(Math.max(d.pnl, 0))}`).join(' ')} ${PL + iW},${zeroY}`;
  const belowPts = `${PL},${zeroY} ${data.map((d, i) => `${tx(i)},${ty(Math.min(d.pnl, 0))}`).join(' ')} ${PL + iW},${zeroY}`;

  const fmtK = v => `$${Math.round(v / 1000)}k`;
  const netAtCenter = data[Math.floor(data.length / 2)]?.pnl ?? 0;

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ color: '#6b7280', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
        Payoff at Expiry {!allFilled && `(${filledCount}/4 legs)`}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 160, display: 'block' }}>
        <rect x="0" y="0" width={W} height={H} fill="#0f172a" rx="6" />
        {/* fills */}
        <polygon points={abovePts} fill="#22c55e" fillOpacity="0.18" />
        <polygon points={belowPts} fill="#ef4444" fillOpacity="0.18" />
        {/* zero line */}
        <line x1={PL} y1={zeroY} x2={W - PR} y2={zeroY} stroke="#374151" strokeWidth="1" strokeDasharray="4,3" />
        {/* curve */}
        <polyline points={pts} fill="none" stroke={netAtCenter >= 0 ? '#22c55e' : '#ef4444'} strokeWidth="2" />
        {/* spot line */}
        <line x1={spotX} y1={PT} x2={spotX} y2={H - PB} stroke="#3b82f6" strokeWidth="1.5" strokeDasharray="5,3" />
        <text x={spotX + 3} y={PT + 10} fill="#3b82f6" fontSize="8">SPOT</text>
        {/* y labels */}
        <text x={PL - 4} y={PT + 8} fill="#6b7280" fontSize="8" textAnchor="end">{maxPnl.toFixed(3)}</text>
        <text x={PL - 4} y={zeroY + 4} fill="#6b7280" fontSize="8" textAnchor="end">0</text>
        <text x={PL - 4} y={H - PB + 4} fill="#6b7280" fontSize="8" textAnchor="end">{minPnl.toFixed(3)}</text>
        {/* x labels */}
        <text x={PL} y={H - 4} fill="#6b7280" fontSize="8" textAnchor="middle">{fmtK(spot * 0.85)}</text>
        <text x={W / 2} y={H - 4} fill="#6b7280" fontSize="8" textAnchor="middle">{fmtK(spot)}</text>
        <text x={W - PR} y={H - 4} fill="#6b7280" fontSize="8" textAnchor="end">{fmtK(spot * 1.15)}</text>
      </svg>
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtExpiry(s) {
  // '22032026' → '22 Mar 2026'
  if (!s || s.length !== 8) return s;
  const months = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const d = s.slice(0, 2), m = parseInt(s.slice(2, 4)), y = s.slice(4);
  return `${d} ${months[m] || m} ${y}`;
}

function computeFinancials(legs, lots) {
  const shortLegs = ['short_ce', 'short_pe'].map(k => legs[k]).filter(Boolean);
  const longLegs  = ['long_ce',  'long_pe' ].map(k => legs[k]).filter(Boolean);
  const grossCredit = shortLegs.reduce((s, l) => s + l.target_premium * l.lots * LOT_SIZE, 0);
  const grossDebit  = longLegs.reduce((s, l)  => s + l.target_premium * l.lots * LOT_SIZE, 0);
  const netCredit   = grossCredit - grossDebit;
  const sc = legs.short_ce, sp = legs.short_pe;
  const breakUpper = sc && netCredit > 0 ? Math.round(sc.strike + netCredit / (lots * LOT_SIZE)) : (sc?.strike ?? null);
  const breakLower = sp && netCredit > 0 ? Math.round(sp.strike - netCredit / (lots * LOT_SIZE)) : (sp?.strike ?? null);
  const maxLoss    = Math.max(grossDebit - grossCredit, 0);
  return { grossCredit, grossDebit, netCredit, maxLoss, breakUpper, breakLower };
}

function fmtBtc(v) {
  if (v == null) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(4)} BTC`;
}
function fmtUsd(v) {
  if (!v) return '—';
  return `$${Number(v).toLocaleString('en-US')}`;
}

// ─── Phase 1: Configure ───────────────────────────────────────────────────────

function ConfigurePhase({ config, onChange, onNext, loading, error }) {
  return (
    <div style={ph.box}>
      <div style={ph.title}>Session Parameters</div>
      {[
        { key: 'lots',          label: 'Initial Lots',          type: 'number', min: 1,   step: 1,    placeholder: '1'    },
        { key: 'sessionWindow', label: 'Session Window (hours)', type: 'number', min: 0.5, step: 0.5,  placeholder: '4'    },
        { key: 'trailingStop',  label: 'Trailing Stop %',        type: 'number', min: 10,  step: 5,    placeholder: '50'   },
        { key: 'maxLoss',       label: 'Max Loss BTC (optional)',type: 'number', min: 0,   step: 0.001,placeholder: 'e.g. 0.05', optional: true },
      ].map(({ key, label, type, min, step, placeholder, optional }) => (
        <div key={key} style={ph.field}>
          <label style={ph.label}>{label}</label>
          <input
            style={ph.input}
            type={type}
            min={min}
            step={step}
            placeholder={placeholder}
            value={config[key]}
            onChange={e => onChange(key, e.target.value)}
          />
        </div>
      ))}
      {error && <div style={ph.error}>{error}</div>}
      <button style={ph.btn} onClick={onNext} disabled={loading}>
        {loading ? 'Loading chain…' : 'Pick Strikes →'}
      </button>
    </div>
  );
}

// ─── Phase 2: Chain picker ────────────────────────────────────────────────────

function LegCard({ legKey, leg, isActive, onClick }) {
  const c = LEG_COLORS[legKey];
  const label = LEG_LABELS[legKey];
  const isShort = legKey.startsWith('short');
  return (
    <div
      onClick={onClick}
      style={{
        border: `1.5px solid ${isActive ? '#f9fafb' : leg ? c.border : '#374151'}`,
        borderRadius: 6,
        padding: '8px 12px',
        cursor: 'pointer',
        background: leg ? c.bg : '#1f2937',
        minWidth: 130,
        opacity: isActive ? 1 : 0.85,
        outline: isActive ? '2px solid #f9fafb' : 'none',
      }}
    >
      <div style={{ fontSize: 10, fontWeight: 700, color: leg ? c.text : '#6b7280', letterSpacing: 0.5, textTransform: 'uppercase' }}>
        {isActive ? `▶ ${label}` : label}
      </div>
      {leg ? (
        <div style={{ fontFamily: 'monospace', fontSize: 13, color: c.text, marginTop: 3 }}>
          K={fmtUsd(leg.strike)} @ ${leg.target_premium}
        </div>
      ) : (
        <div style={{ fontSize: 11, color: '#4b5563', marginTop: 3 }}>
          {isActive ? 'click a row ↓' : 'pending'}
        </div>
      )}
    </div>
  );
}

function ChainPhase({ config, expirations, expiry, setExpiry, chainData, loadingChain, legs, activeLeg, onLegCardClick, onChainRowClick, onBack, onConfirm }) {
  const spots = chainData?.spot_price ?? 0;
  const atm = chainData?.atm_strike ?? 0;
  const allFilled = LEG_SEQUENCE.every(k => legs[k]);

  // Filter chain to ±15% of ATM
  const chain = useMemo(() => {
    if (!chainData?.chain) return [];
    return chainData.chain.filter(row => {
      const s = row.strike;
      return s >= atm * 0.85 && s <= atm * 1.15;
    });
  }, [chainData, atm]);

  const fin = useMemo(() => computeFinancials(legs, parseInt(config.lots) || 1), [legs, config.lots]);

  const getRowLegHighlight = (strike) => {
    const results = { ce: null, pe: null };
    if (legs.short_ce?.strike === strike) results.ce = 'short';
    if (legs.long_ce?.strike  === strike) results.ce = 'long';
    if (legs.short_pe?.strike === strike) results.pe = 'short';
    if (legs.long_pe?.strike  === strike) results.pe = 'long';
    return results;
  };

  return (
    <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
      {/* Left: structure builder */}
      <div style={{ minWidth: 220, maxWidth: 260, flex: '0 0 240px' }}>
        <div style={ch.sectionTitle}>Structure</div>

        {/* Leg cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
          {LEG_SEQUENCE.map(key => (
            <LegCard
              key={key}
              legKey={key}
              leg={legs[key]}
              isActive={activeLeg === key}
              onClick={() => onLegCardClick(key)}
            />
          ))}
        </div>

        {/* Financials */}
        {(legs.short_ce || legs.short_pe) && (
          <div style={ch.finBox}>
            <FinRow label="Gross Credit"  value={fmtBtc(fin.grossCredit)} color="#22c55e" />
            <FinRow label="Gross Debit"   value={fmtBtc(-fin.grossDebit)} color="#ef4444" />
            <div style={{ borderTop: '1px solid #374151', margin: '6px 0' }} />
            <FinRow label="Net Credit"    value={fmtBtc(fin.netCredit)}   color={fin.netCredit >= 0 ? '#22c55e' : '#ef4444'} bold />
            {fin.breakUpper && <FinRow label="Upper BE"  value={fmtUsd(fin.breakUpper)} />}
            {fin.breakLower && <FinRow label="Lower BE"  value={fmtUsd(fin.breakLower)} />}
          </div>
        )}

        {/* Payoff graph */}
        {spots > 0 && <PayoffGraph legs={legs} spot={spots} />}

        {/* Buttons */}
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <button style={ch.backBtn} onClick={onBack}>← Back</button>
          <button style={{ ...ch.confirmBtn, opacity: allFilled ? 1 : 0.4 }} onClick={onConfirm} disabled={!allFilled}>
            Confirm →
          </button>
        </div>
      </div>

      {/* Right: chain table */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Expiry + spot bar */}
        <div style={ch.chainHeader}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={ch.label}>EXPIRY</span>
            <select style={ch.select} value={expiry} onChange={e => setExpiry(e.target.value)}>
              {expirations.map(exp => (
                <option key={exp} value={exp}>{fmtExpiry(exp)}</option>
              ))}
            </select>
          </div>
          <div style={{ color: '#9ca3af', fontSize: 13 }}>
            Spot: <strong style={{ color: '#f9fafb' }}>{fmtUsd(spots)}</strong>
          </div>
        </div>

        {/* Active leg indicator */}
        <div style={ch.activeLegBar}>
          Active: &nbsp;
          {LEG_SEQUENCE.map(key => (
            <span
              key={key}
              style={{
                ...ch.activePill,
                background: activeLeg === key ? '#1d4ed8' : '#1f2937',
                color: activeLeg === key ? '#fff' : '#6b7280',
                fontWeight: activeLeg === key ? 700 : 400,
                cursor: 'pointer',
              }}
              onClick={() => onLegCardClick(key)}
            >
              {LEG_LABELS[key]}
            </span>
          ))}
        </div>

        {/* Chain table */}
        {loadingChain ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>Loading chain…</div>
        ) : (
          <div style={{ overflowX: 'auto', maxHeight: 460, overflowY: 'auto' }}>
            <table style={ch.table}>
              <thead>
                <tr style={{ background: '#0f172a', position: 'sticky', top: 0, zIndex: 1 }}>
                  <th style={ch.th}>STRIKE</th>
                  <th style={ch.th}>CE BID</th>
                  <th style={ch.th}>CE ASK</th>
                  <th style={ch.th}>CE IV%</th>
                  <th style={{ ...ch.th, textAlign: 'center' }}>CE ACTION</th>
                  <th style={{ ...ch.th, textAlign: 'center' }}>PE ACTION</th>
                  <th style={ch.th}>PE BID</th>
                  <th style={ch.th}>PE ASK</th>
                  <th style={ch.th}>PE IV%</th>
                </tr>
              </thead>
              <tbody>
                {chain.map(row => {
                  const strike = row.strike;
                  const ce = row.call || {};
                  const pe = row.put  || {};
                  const hl = getRowLegHighlight(strike);
                  const isAtm = strike === atm;

                  const ceBg = hl.ce === 'short' ? '#450a0a' : hl.ce === 'long' ? '#052e16' : 'transparent';
                  const peBg = hl.pe === 'short' ? '#450a0a' : hl.pe === 'long' ? '#052e16' : 'transparent';

                  return (
                    <tr key={strike} style={{
                      borderBottom: '1px solid #1f2937',
                      background: isAtm ? '#1a1a00' : '#111827',
                      outline: isAtm ? '1px solid #854d0e' : 'none',
                    }}>
                      {/* Strike */}
                      <td style={{ ...ch.td, fontWeight: 700, color: isAtm ? '#fbbf24' : '#f9fafb', fontFamily: 'monospace' }}>
                        {fmtUsd(strike)}{isAtm && <span style={{ color: '#fbbf24', fontSize: 9, marginLeft: 4 }}>ATM</span>}
                      </td>
                      {/* CE data */}
                      <td style={{ ...ch.td, background: ceBg, fontFamily: 'monospace', color: '#4ade80' }}>
                        {ce.bid ? `$${ce.bid}` : '—'}
                      </td>
                      <td style={{ ...ch.td, background: ceBg, fontFamily: 'monospace', color: '#f87171' }}>
                        {ce.ask ? `$${ce.ask}` : '—'}
                      </td>
                      <td style={{ ...ch.td, background: ceBg, color: '#9ca3af' }}>
                        {ce.iv ? `${(ce.iv * 100).toFixed(0)}%` : '—'}
                      </td>
                      {/* CE actions */}
                      <td style={{ ...ch.td, textAlign: 'center', background: ceBg }}>
                        {ce.bid > 0 && <button style={ch.sellBtn} onClick={() => onChainRowClick(row, 'short_ce')}>Sell</button>}
                        {ce.ask > 0 && <button style={ch.buyBtn}  onClick={() => onChainRowClick(row, 'long_ce')}>Buy</button>}
                      </td>
                      {/* PE actions */}
                      <td style={{ ...ch.td, textAlign: 'center', background: peBg }}>
                        {pe.bid > 0 && <button style={ch.sellBtn} onClick={() => onChainRowClick(row, 'short_pe')}>Sell</button>}
                        {pe.ask > 0 && <button style={ch.buyBtn}  onClick={() => onChainRowClick(row, 'long_pe')}>Buy</button>}
                      </td>
                      {/* PE data */}
                      <td style={{ ...ch.td, background: peBg, fontFamily: 'monospace', color: '#4ade80' }}>
                        {pe.bid ? `$${pe.bid}` : '—'}
                      </td>
                      <td style={{ ...ch.td, background: peBg, fontFamily: 'monospace', color: '#f87171' }}>
                        {pe.ask ? `$${pe.ask}` : '—'}
                      </td>
                      <td style={{ ...ch.td, background: peBg, color: '#9ca3af' }}>
                        {pe.iv ? `${(pe.iv * 100).toFixed(0)}%` : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function FinRow({ label, value, color, bold }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
      <span style={{ color: '#6b7280', fontSize: 12 }}>{label}</span>
      <span style={{ color: color || '#e5e7eb', fontSize: 12, fontFamily: 'monospace', fontWeight: bold ? 700 : 400 }}>{value}</span>
    </div>
  );
}

// ─── Phase 3: Confirm ─────────────────────────────────────────────────────────

function ConfirmPhase({ legs, config, expiry, onBack, onExecute, executing, error }) {
  const lots = parseInt(config.lots) || 1;
  const fin  = computeFinancials(legs, lots);

  return (
    <div style={ph.box}>
      <div style={ph.title}>Confirm Entry — {fmtExpiry(expiry)}</div>

      {/* Leg cards */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        {LEG_SEQUENCE.map(key => {
          const leg = legs[key];
          const c = LEG_COLORS[key];
          if (!leg) return null;
          return (
            <div key={key} style={{ background: c.bg, border: `1px solid ${c.border}`, borderRadius: 6, padding: '10px 14px', flex: '1 1 140px' }}>
              <div style={{ color: c.text, fontSize: 10, fontWeight: 700, letterSpacing: 0.5 }}>{LEG_LABELS[key]}</div>
              <div style={{ color: '#f9fafb', fontFamily: 'monospace', fontSize: 14, marginTop: 4 }}>{fmtUsd(leg.strike)}</div>
              <div style={{ color: '#9ca3af', fontSize: 12, marginTop: 2 }}>{leg.lots} lot{leg.lots > 1 ? 's' : ''} @ ${leg.target_premium}</div>
              <div style={{ color: '#6b7280', fontSize: 11, marginTop: 2 }}>{leg.symbol}</div>
            </div>
          );
        })}
      </div>

      {/* Financials */}
      <div style={{ background: '#1f2937', borderRadius: 6, padding: '12px 16px', marginBottom: 16 }}>
        <FinRow label="Gross Credit (shorts)"    value={fmtBtc(fin.grossCredit)}  color="#22c55e" />
        <FinRow label="Gross Debit (hedges)"     value={fmtBtc(-fin.grossDebit)}  color="#ef4444" />
        <div style={{ borderTop: '1px solid #374151', margin: '6px 0' }} />
        <FinRow label="Net Credit"               value={fmtBtc(fin.netCredit)}    color={fin.netCredit >= 0 ? '#22c55e' : '#ef4444'} bold />
        <FinRow label="Est. Max Loss"            value={fmtBtc(-fin.maxLoss * 1.75)} color="#ef4444" />
        <FinRow label="Breakeven Upper"          value={fmtUsd(fin.breakUpper)} />
        <FinRow label="Breakeven Lower"          value={fmtUsd(fin.breakLower)} />
        <div style={{ borderTop: '1px solid #374151', margin: '6px 0' }} />
        <FinRow label="Session Window"           value={`${config.sessionWindow}h`} />
        <FinRow label="Trailing Stop"            value={`${config.trailingStop}% of peak`} />
        {config.maxLoss && <FinRow label="Max Loss Override" value={`${config.maxLoss} BTC`} />}
      </div>

      {error && <div style={ph.error}>{error}</div>}

      <div style={{ display: 'flex', gap: 8 }}>
        <button style={{ ...ph.btn, background: '#374151', flex: '0 0 auto', width: 100 }} onClick={onBack} disabled={executing}>← Back</button>
        <button style={{ ...ph.btn, background: '#15803d', flex: 1 }} onClick={onExecute} disabled={executing}>
          {executing ? 'Placing 4 legs…' : '✓ Execute Entry'}
        </button>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function SSDHSessionCreate({ onSessionStarted }) {
  const [phase, setPhase]               = useState('configure');
  const [config, setConfig]             = useState({ lots: 1, sessionWindow: 4, trailingStop: 50, maxLoss: '' });
  const [expirations, setExpirations]   = useState([]);
  const [expiry, setExpiry]             = useState('');
  const [chainData, setChainData]       = useState(null);
  const [loadingChain, setLoadingChain] = useState(false);
  const [legs, setLegs]                 = useState({ short_ce: null, short_pe: null, long_ce: null, long_pe: null });
  const [activeLeg, setActiveLeg]       = useState('short_ce');
  const [executing, setExecuting]       = useState(false);
  const [error, setError]               = useState('');
  const [loading, setLoading]           = useState(false);

  // Fetch chain when expiry changes
  const fetchChain = useCallback(async (exp) => {
    if (!exp) return;
    setLoadingChain(true);
    try {
      const res  = await fetch(`/api/options-chain/data?underlying=BTC&expiry=${exp}`);
      const data = await res.json();
      setChainData(data);
    } catch (e) {
      setError('Chain fetch failed: ' + e.message);
    } finally {
      setLoadingChain(false);
    }
  }, []);

  useEffect(() => {
    if (expiry) fetchChain(expiry);
  }, [expiry, fetchChain]);

  const handleConfigChange = (key, val) => setConfig(prev => ({ ...prev, [key]: val }));

  const handlePickStrikes = async () => {
    setError('');
    setLoading(true);
    try {
      const res  = await fetch('/api/options-chain/expirations?underlying=BTC');
      const data = await res.json();
      const exps = data.expirations || [];
      setExpirations(exps);
      if (exps.length) {
        setExpiry(exps[0]);
        await fetchChain(exps[0]);
      }
      setPhase('chain');
    } catch (e) {
      setError('Failed to load expirations: ' + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLegCardClick = (key) => setActiveLeg(key);

  const handleChainRowClick = (row, legKey) => {
    const lots   = parseInt(config.lots) || 1;
    const isShort = legKey.startsWith('short');
    const isCE    = legKey.endsWith('ce');
    const side    = isCE ? 'CE' : 'PE';
    const opt     = isCE ? (row.call || {}) : (row.put || {});

    const price  = isShort ? (opt.bid || opt.mark_price || 0) : (opt.ask || opt.mark_price || 0);
    const legLots = isShort ? lots : lots * 2;

    setLegs(prev => ({
      ...prev,
      [legKey]: {
        leg_id:         legKey,
        side,
        direction:      isShort ? 'short' : 'long',
        pos_type:       isShort ? 'core' : 'hedge',
        strike:         row.strike,
        lots:           legLots,
        target_premium: price,
        symbol:         opt.symbol || '',
      },
    }));

    // Auto-advance active leg to next unfilled
    const idx = LEG_SEQUENCE.indexOf(legKey);
    const next = LEG_SEQUENCE.slice(idx + 1).find(k => !legs[k] || k === legKey);
    if (next && next !== legKey) setActiveLeg(next);
    else {
      const nextUnfilled = LEG_SEQUENCE.find(k => k !== legKey && !legs[k]);
      if (nextUnfilled) setActiveLeg(nextUnfilled);
    }
  };

  const handleConfirm = () => {
    if (!LEG_SEQUENCE.every(k => legs[k])) { setError('All 4 legs must be selected'); return; }
    setPhase('confirm');
    setError('');
  };

  const handleExecute = async () => {
    setExecuting(true);
    setError('');
    try {
      const body = {
        confirm:            true,
        legs:               LEG_SEQUENCE.map(k => legs[k]),
        initial_lots:       parseInt(config.lots) || 1,
        expiry,
        session_window_hours: parseFloat(config.sessionWindow) || 4,
        trailing_stop_pct:  (parseFloat(config.trailingStop) || 50) / 100,
        ...(config.maxLoss ? { max_loss_amount: parseFloat(config.maxLoss) } : {}),
      };
      const res  = await fetch('/api/ssdh/sessions/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || data.details || 'Start failed');
      if (onSessionStarted) onSessionStarted(data.session_id);
      setPhase('configure');
      setLegs({ short_ce: null, short_pe: null, long_ce: null, long_pe: null });
    } catch (e) {
      setError(e.message);
      setExecuting(false);
    }
  };

  if (phase === 'configure') {
    return <ConfigurePhase config={config} onChange={handleConfigChange} onNext={handlePickStrikes} loading={loading} error={error} />;
  }

  if (phase === 'chain') {
    return (
      <div style={{ padding: '0 0 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <div style={{ color: '#f9fafb', fontSize: 16, fontWeight: 700 }}>Select Option Strikes</div>
        </div>
        <ChainPhase
          config={config}
          expirations={expirations}
          expiry={expiry}
          setExpiry={exp => { setExpiry(exp); setChainData(null); }}
          chainData={chainData}
          loadingChain={loadingChain}
          legs={legs}
          activeLeg={activeLeg}
          onLegCardClick={handleLegCardClick}
          onChainRowClick={handleChainRowClick}
          onBack={() => setPhase('configure')}
          onConfirm={handleConfirm}
        />
        {error && <div style={{ ...ph.error, marginTop: 8 }}>{error}</div>}
      </div>
    );
  }

  if (phase === 'confirm') {
    return <ConfirmPhase legs={legs} config={config} expiry={expiry} onBack={() => setPhase('chain')} onExecute={handleExecute} executing={executing} error={error} />;
  }

  return (
    <div style={{ padding: 32, textAlign: 'center', color: '#fbbf24', fontSize: 14 }}>
      Placing 4 legs simultaneously… Monitor dashboard for fill confirmation.
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const ph = {
  box:   { background: '#111827', borderRadius: 8, padding: 20, maxWidth: 420 },
  title: { color: '#f9fafb', fontSize: 15, fontWeight: 700, marginBottom: 16 },
  field: { marginBottom: 12 },
  label: { display: 'block', color: '#9ca3af', fontSize: 11, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 },
  input: { width: '100%', background: '#1f2937', border: '1px solid #374151', borderRadius: 4, padding: '8px 10px', color: '#f9fafb', fontSize: 14, boxSizing: 'border-box' },
  btn:   { width: '100%', marginTop: 8, padding: '10px', background: '#1d4ed8', color: '#fff', border: 'none', borderRadius: 6, fontSize: 14, fontWeight: 600, cursor: 'pointer' },
  error: { color: '#f87171', fontSize: 13, padding: '6px 0' },
};

const ch = {
  sectionTitle: { color: '#9ca3af', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 },
  finBox:       { background: '#1f2937', borderRadius: 6, padding: '10px 12px', marginBottom: 12 },
  backBtn:      { padding: '8px 14px', background: '#374151', color: '#d1d5db', border: 'none', borderRadius: 5, cursor: 'pointer', fontSize: 13 },
  confirmBtn:   { flex: 1, padding: '8px 16px', background: '#15803d', color: '#fff', border: 'none', borderRadius: 5, cursor: 'pointer', fontSize: 13, fontWeight: 700 },
  chainHeader:  { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  label:        { color: '#9ca3af', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5 },
  select:       { background: '#1f2937', border: '1px solid #374151', borderRadius: 4, color: '#f9fafb', padding: '5px 8px', fontSize: 13 },
  activeLegBar: { display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, fontSize: 11, color: '#6b7280' },
  activePill:   { padding: '3px 8px', borderRadius: 4, fontSize: 10, letterSpacing: 0.5, textTransform: 'uppercase' },
  table:        { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
  th:           { padding: '7px 10px', color: '#6b7280', fontWeight: 600, fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5, borderBottom: '1px solid #374151', textAlign: 'left', whiteSpace: 'nowrap' },
  td:           { padding: '7px 10px', borderBottom: '1px solid #1f2937', whiteSpace: 'nowrap' },
  sellBtn:      { padding: '3px 8px', background: '#7f1d1d', color: '#fca5a5', border: '1px solid #991b1b', borderRadius: 3, cursor: 'pointer', fontSize: 11, fontWeight: 700, marginRight: 4 },
  buyBtn:       { padding: '3px 8px', background: '#052e16', color: '#86efac', border: '1px solid #166534', borderRadius: 3, cursor: 'pointer', fontSize: 11, fontWeight: 700 },
};
