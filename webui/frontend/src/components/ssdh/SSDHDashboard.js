/**
 * SSDHDashboard — Main dashboard for SSDH sessions
 *
 * Landing page (no active session):
 *   Hero: strategy name + description + anatomy SVG + feature pills
 *   Stats bar: sessions run, win rate, lifetime P&L, best session
 *   Session history table: last 8 sessions
 *   Launch CTA button
 *
 * Create wizard: SSDHSessionCreate (opens on demand, not on load)
 *
 * Active session view:
 *   SSDHStatusBanner → SSDHPositionsTable | SSDHPnLPanel + SSDHActivityLog
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import ssdh_service from './ssdh_service';
import SSDHStatusBanner from './SSDHStatusBanner';
import SSDHPositionsTable from './SSDHPositionsTable';
import SSDHPnLPanel from './SSDHPnLPanel';
import SSDHActivityLog from './SSDHActivityLog';
import SSDHSessionCreate from './SSDHSessionCreate';
import { readWarmJSON, setWarmJSON } from '../../utils/dataWarmCache';

const POLL_MS = 10000;
const LIVE_STATUSES = ['RUNNING', 'WIND_DOWN', 'INITIALIZING', 'EMERGENCY'];

// ─── Strategy anatomy diagram ──────────────────────────────────────────────────

function StrategyAnatomy() {
  return (
    <div style={an.wrap}>
      <svg viewBox="0 0 320 148" style={{ width: '100%', maxWidth: 340, height: 148, display: 'block', margin: '0 auto' }}>
        <defs>
          <linearGradient id="sg_profit" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity="0.30" />
            <stop offset="100%" stopColor="#10b981" stopOpacity="0.04" />
          </linearGradient>
          <linearGradient id="sg_loss_l" x1="1" y1="0" x2="0" y2="0">
            <stop offset="0%" stopColor="#ef4444" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#ef4444" stopOpacity="0.04" />
          </linearGradient>
          <linearGradient id="sg_loss_r" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#ef4444" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#ef4444" stopOpacity="0.04" />
          </linearGradient>
        </defs>

        {/* Zero axis */}
        <line x1="12" y1="84" x2="308" y2="84" stroke="#374151" strokeWidth="1" />

        {/* Loss zone fills (capped by wings) */}
        <polygon points="12,120 42,84 42,120" fill="url(#sg_loss_l)" />
        <polygon points="278,84 308,120 278,120" fill="url(#sg_loss_r)" />

        {/* Profit tent fill */}
        <polygon points="42,84 100,34 220,34 278,84" fill="url(#sg_profit)" />

        {/* Profit tent outline */}
        <polyline points="42,84 100,34 220,34 278,84"
          fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinejoin="round" />

        {/* Loss wings — capped (flat bottom = hedge protection) */}
        <polyline points="12,120 42,84" fill="none" stroke="#ef4444" strokeWidth="2" />
        <polyline points="278,84 308,120" fill="none" stroke="#ef4444" strokeWidth="2" />
        {/* Wing cap horizontals */}
        <line x1="12" y1="120" x2="42" y2="120" stroke="#22c55e" strokeWidth="2.5" strokeLinecap="round" />
        <line x1="278" y1="120" x2="308" y2="120" stroke="#22c55e" strokeWidth="2.5" strokeLinecap="round" />

        {/* ATM spot dot */}
        <line x1="160" y1="34" x2="160" y2="84" stroke="#4b5563" strokeWidth="1" strokeDasharray="3,2" />
        <circle cx="160" cy="84" r="3.5" fill="#6b7280" />

        {/* Labels — SHORT legs */}
        <rect x="71" y="18" width="57" height="16" rx="3" fill="#450a0a" />
        <text x="100" y="30" textAnchor="middle" fill="#fca5a5" fontSize="9.5" fontWeight="700" fontFamily="monospace">SELL PE</text>

        <rect x="193" y="18" width="57" height="16" rx="3" fill="#450a0a" />
        <text x="221" y="30" textAnchor="middle" fill="#fca5a5" fontSize="9.5" fontWeight="700" fontFamily="monospace">SELL CE</text>

        {/* Labels — LONG hedge legs */}
        <rect x="10" y="130" width="56" height="16" rx="3" fill="#052e16" />
        <text x="38" y="142" textAnchor="middle" fill="#86efac" fontSize="9.5" fontWeight="700" fontFamily="monospace">BUY PE</text>

        <rect x="255" y="130" width="56" height="16" rx="3" fill="#052e16" />
        <text x="283" y="142" textAnchor="middle" fill="#86efac" fontSize="9.5" fontWeight="700" fontFamily="monospace">BUY CE</text>

        {/* ATM label */}
        <text x="160" y="11" textAnchor="middle" fill="#6b7280" fontSize="8.5" fontFamily="monospace">ATM</text>

        {/* Net credit label in tent */}
        <text x="160" y="62" textAnchor="middle" fill="#34d399" fontSize="9" opacity="0.9">net credit collected</text>
      </svg>

      <div style={an.tagRow}>
        <span style={an.tagRed}>● Short ATM straddle</span>
        <span style={an.tagGreen}>● Long OTM wings</span>
      </div>
    </div>
  );
}

// ─── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, color = '#f9fafb', sub }) {
  return (
    <div style={sc.card}>
      <div style={{ ...sc.value, color }}>{value}</div>
      <div style={sc.label}>{label}</div>
      {sub && <div style={sc.sub}>{sub}</div>}
    </div>
  );
}

// ─── History row ───────────────────────────────────────────────────────────────

function HistoryRow({ session, isActive, onClick }) {
  const pnl = session.net_pnl ?? null;
  const statusColor = {
    RUNNING: '#10b981', INITIALIZING: '#f59e0b', WIND_DOWN: '#f97316',
    CLOSED: '#6b7280',  ABORTED: '#ef4444',      EMERGENCY: '#dc2626',
  }[session.status] || '#6b7280';

  const fmtDate = (id) => {
    // session_id includes timestamp — use created_at if available
    if (session.created_at) {
      const d = new Date(session.created_at * 1000);
      return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
    }
    return id.slice(-8);
  };

  return (
    <div
      style={{ ...hr.row, borderColor: isActive ? '#3b82f6' : '#1f2937', background: isActive ? '#1e3a5f22' : '#111827' }}
      onClick={onClick}
    >
      <span style={hr.id}>{session.session_id.slice(-8)}</span>
      <span style={{ ...hr.status, color: statusColor }}>{session.status}</span>
      <span style={hr.date}>{fmtDate(session.session_id)}</span>
      <span style={{ ...hr.pnl, color: pnl == null ? '#6b7280' : pnl >= 0 ? '#22c55e' : '#ef4444' }}>
        {pnl != null ? `${pnl >= 0 ? '+' : ''}${pnl.toFixed(4)} ₿` : '—'}
      </span>
      {session.close_reason
        ? <span style={hr.reason}>{session.close_reason}</span>
        : <span style={hr.reason}>—</span>
      }
    </div>
  );
}

// ─── Landing page ──────────────────────────────────────────────────────────────

function SSDHLandingPage({ sessions, onLaunch, onSelectSession, activeSession }) {
  const closed   = sessions.filter(s => s.status === 'CLOSED');
  const wins     = closed.filter(s => (s.net_pnl ?? 0) > 0).length;
  const lifetime = closed.reduce((acc, s) => acc + (s.net_pnl ?? 0), 0);
  const best     = closed.length ? Math.max(...closed.map(s => s.net_pnl ?? 0)) : null;
  const winRate  = closed.length ? Math.round((wins / closed.length) * 100) : null;

  const features = [
    '4-leg atomic entry',
    'Adaptive heartbeat',
    'Vega spike detection',
    'Trailing stop',
    'Kill switch',
    'Crash recovery',
  ];

  return (
    <div style={lp.page}>

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div style={lp.hero}>
        <div style={lp.heroLeft}>
          <div style={lp.badge}>DELTA EXCHANGE · OPTIONS</div>
          <h1 style={lp.heroTitle}>
            Short Straddle
            <br />
            <span style={{ color: '#60a5fa' }}>Double Hedge</span>
          </h1>
          <p style={lp.heroDesc}>
            Sell an ATM straddle to collect premium. Buy OTM wings on both sides
            to cap maximum loss. An adaptive monitor tracks trailing stop, vega spikes,
            margin, and structure integrity every heartbeat.
          </p>
          <div style={lp.features}>
            {features.map(f => (
              <span key={f} style={lp.pill}>✓ {f}</span>
            ))}
          </div>
          <button style={lp.launchBtn} onClick={onLaunch}>
            ⚡ Launch SSDH Session
          </button>
        </div>

        <div style={lp.heroRight}>
          <div style={lp.anatomyCard}>
            <div style={lp.anatomyLabel}>STRATEGY STRUCTURE</div>
            <StrategyAnatomy />
            <div style={lp.anatomyFooter}>
              <div style={lp.aFootItem}>
                <div style={{ ...lp.aFootDot, background: '#dc2626' }} />
                <div>
                  <div style={lp.aFootTitle}>Short ATM Straddle</div>
                  <div style={lp.aFootSub}>Collect premium — core income</div>
                </div>
              </div>
              <div style={lp.aFootItem}>
                <div style={{ ...lp.aFootDot, background: '#16a34a' }} />
                <div>
                  <div style={lp.aFootTitle}>Long OTM Wings</div>
                  <div style={lp.aFootSub}>Define max loss — hedge protection</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Stats bar (only if history exists) ───────────────────────────── */}
      {closed.length > 0 && (
        <div style={lp.statsBar}>
          <StatCard label="Sessions Run" value={sessions.length} />
          <StatCard
            label="Win Rate"
            value={winRate != null ? `${winRate}%` : '—'}
            color={winRate != null ? (winRate >= 50 ? '#10b981' : '#f97316') : '#6b7280'}
            sub={`${wins} / ${closed.length} closed`}
          />
          <StatCard
            label="Lifetime P&L"
            value={`${lifetime >= 0 ? '+' : ''}${lifetime.toFixed(4)} ₿`}
            color={lifetime >= 0 ? '#10b981' : '#ef4444'}
          />
          {best != null && (
            <StatCard
              label="Best Session"
              value={`+${best.toFixed(4)} ₿`}
              color="#10b981"
            />
          )}
        </div>
      )}

      {/* ── Session history ───────────────────────────────────────────────── */}
      {sessions.length > 0 && (
        <div style={lp.histSection}>
          <div style={lp.sectionLabel}>RECENT SESSIONS</div>
          <div style={hr.header}>
            <span style={hr.hId}>Session</span>
            <span style={hr.hStatus}>Status</span>
            <span style={hr.hDate}>Date</span>
            <span style={hr.hPnl}>P&L</span>
            <span style={hr.hReason}>Exit reason</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {sessions.slice(0, 8).map(ss => (
              <HistoryRow
                key={ss.session_id}
                session={ss}
                isActive={activeSession?.session_id === ss.session_id}
                onClick={() => onSelectSession(ss.session_id)}
              />
            ))}
          </div>
        </div>
      )}

      {sessions.length === 0 && (
        <div style={lp.noHistory}>
          No sessions yet — launch your first one above.
        </div>
      )}
    </div>
  );
}

// ─── Main dashboard ────────────────────────────────────────────────────────────

export default function SSDHDashboard() {
  const [sessions, setSessions]       = useState(() => readWarmJSON('/api/ssdh/sessions')?.sessions || []);
  const [activeSession, setActive]    = useState(null);
  const [showCreate, setShowCreate]   = useState(false);
  const [vegaSpike, setVegaSpike]     = useState(false);
  const [structureOk, setStructureOk] = useState(true);
  const [killConfirm, setKillConfirm] = useState(false);
  const [killing, setKilling]         = useState(false);
  const [error, setError]             = useState('');
  const pollRef = useRef(null);

  // ── Data loading ─────────────────────────────────────────────────────────────
  const loadSessions = useCallback(async () => {
    try {
      const data = await ssdh_service.getSessions();
      setWarmJSON('/api/ssdh/sessions', data, { ttlMs: 12000 });

      const list = data.sessions || [];
      setSessions(list);
      const live = list.find(s => LIVE_STATUSES.includes(s.status));
      if (live && (!activeSession || activeSession.session_id !== live.session_id)) {
        const d = await ssdh_service.getSession(live.session_id);
        setActive(d.session);
      }
    } catch {}
  }, [activeSession]);

  useEffect(() => {
    loadSessions();
    pollRef.current = setInterval(loadSessions, POLL_MS);
    return () => clearInterval(pollRef.current);
  }, [loadSessions]);

  // ── WebSocket ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    const unsubs = [
      ssdh_service.on('ssdh_state_update', d => {
        setActive(prev => (!prev || prev.session_id !== d.session_id) ? prev : { ...prev, ...d });
        setStructureOk(d.structure_ok !== false);
      }),
      ssdh_service.on('ssdh_structure_break', () => setStructureOk(false)),
      ssdh_service.on('ssdh_vega_spike',      () => { setVegaSpike(true); setTimeout(() => setVegaSpike(false), 60000); }),
      ssdh_service.on('ssdh_session_closed',  () => { loadSessions(); setStructureOk(true); setVegaSpike(false); }),
      ssdh_service.on('ssdh_kill_switch',     () => setKilling(false)),
      ssdh_service.on('ssdh_leg_entry',       () => setTimeout(loadSessions, 1200)),
    ];
    return () => unsubs.forEach(fn => fn && fn());
  }, [loadSessions]);

  // ── Kill switch ───────────────────────────────────────────────────────────────
  const handleKill = async () => {
    if (!activeSession) return;
    setKilling(true); setKillConfirm(false); setError('');
    try { await ssdh_service.killSession(activeSession.session_id); }
    catch (e) { setError(e?.response?.data?.error || 'Kill failed'); setKilling(false); }
  };

  const handleSelectSession = async (sid) => {
    try { const d = await ssdh_service.getSession(sid); setActive(d.session); }
    catch (e) { setError(e.message); }
  };

  const isLive = activeSession && LIVE_STATUSES.includes(activeSession?.status);

  // ── Which view to show ────────────────────────────────────────────────────────
  // showCreate   → wizard
  // activeSession (and not showCreate) → session detail view
  // else → landing page

  return (
    <div style={s.page}>

      {/* ── Global top bar ─────────────────────────────────────────────────── */}
      <div style={s.topBar}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {activeSession && !showCreate && (
            <button style={s.backBtn} onClick={() => setActive(null)}>← Overview</button>
          )}
          <div>
            <h2 style={s.title}>SSDH Engine</h2>
            <span style={s.subtitle}>Short Straddle Double Hedge</span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {showCreate
            ? <button style={s.cancelBtn} onClick={() => setShowCreate(false)}>✕ Cancel</button>
            : <button style={s.newBtn}    onClick={() => setShowCreate(true)}>⚡ New Session</button>
          }
          {isLive && !showCreate && !killing && (
            <button style={s.killBtn} onClick={() => setKillConfirm(true)}>☠ Kill</button>
          )}
          {killing && <span style={{ color: '#ef4444', fontSize: 13 }}>Killing…</span>}
        </div>
      </div>

      {error && <div style={s.errBanner}>{error}</div>}

      {/* ── Kill confirm dialog ─────────────────────────────────────────────── */}
      {killConfirm && (
        <div style={s.dialog}>
          <strong style={{ color: '#fca5a5' }}>⚠ Emergency Kill Switch</strong>
          <p style={{ color: '#d1d5db', margin: '8px 0', fontSize: 13 }}>
            Closes ALL 4 positions at market immediately. No conditions. No waiting.
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <button style={s.dialogKillBtn}   onClick={handleKill}>Confirm — Close All at Market</button>
            <button style={s.dialogCancelBtn} onClick={() => setKillConfirm(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* ── Create wizard ───────────────────────────────────────────────────── */}
      {showCreate && (
        <SSDHSessionCreate
          onSessionStarted={sid => {
            setShowCreate(false);
            setTimeout(() => handleSelectSession(sid), 2000);
          }}
        />
      )}

      {/* ── Active / historical session detail ─────────────────────────────── */}
      {!showCreate && activeSession && (
        <>
          <div style={{ marginBottom: 16 }}>
            <SSDHStatusBanner session={activeSession} vegaSpike={vegaSpike} structureOk={structureOk} />
          </div>
          <div style={s.grid}>
            <div style={s.posCol}>
              <div style={s.colTitle}>Positions</div>
              <SSDHPositionsTable positions={activeSession.positions || []} structureOk={structureOk} />
              {isLive && (
                <button style={s.gracefulBtn} onClick={async () => {
                  try { await ssdh_service.stopSession(activeSession.session_id); }
                  catch (e) { setError(e.message); }
                }}>
                  Graceful Exit
                </button>
              )}
            </div>
            <div style={s.rightCol}>
              <SSDHPnLPanel session={activeSession} params={activeSession.params} />
              <div style={{ marginTop: 12 }}>
                <SSDHActivityLog sessionId={activeSession.session_id} />
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── Landing page ────────────────────────────────────────────────────── */}
      {!showCreate && !activeSession && (
        <SSDHLandingPage
          sessions={sessions}
          onLaunch={() => setShowCreate(true)}
          onSelectSession={handleSelectSession}
          activeSession={activeSession}
        />
      )}
    </div>
  );
}

// ─── Styles ────────────────────────────────────────────────────────────────────

const s = {
  page:           { padding: '20px 24px', maxWidth: 1200, margin: '0 auto' },
  topBar:         { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 },
  title:          { color: '#f9fafb', fontSize: 22, fontWeight: 800, margin: 0 },
  subtitle:       { color: '#6b7280', fontSize: 13 },
  newBtn:         { padding: '8px 16px', background: '#1d4ed8', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 13 },
  cancelBtn:      { padding: '8px 16px', background: '#374151', color: '#d1d5db', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 },
  backBtn:        { padding: '6px 12px', background: 'transparent', color: '#6b7280', border: '1px solid #374151', borderRadius: 6, cursor: 'pointer', fontSize: 12 },
  killBtn:        { padding: '8px 14px', background: '#991b1b', color: '#fca5a5', border: '1px solid #7f1d1d', borderRadius: 6, cursor: 'pointer', fontWeight: 700, fontSize: 13 },
  errBanner:      { color: '#f87171', background: '#1c0a0a', border: '1px solid #7f1d1d', borderRadius: 6, padding: '10px 14px', marginBottom: 12, fontSize: 13 },
  dialog:         { background: '#1c0a0a', border: '1px solid #7f1d1d', borderRadius: 8, padding: '16px 20px', marginBottom: 16 },
  dialogKillBtn:  { padding: '8px 16px', background: '#7f1d1d', color: '#fca5a5', border: '1px solid #991b1b', borderRadius: 6, cursor: 'pointer', fontWeight: 700, fontSize: 13 },
  dialogCancelBtn:{ padding: '8px 16px', background: '#374151', color: '#d1d5db', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 },
  grid:           { display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' },
  posCol:         { flex: '1 1 380px', minWidth: 0 },
  rightCol:       { flex: '0 0 300px', minWidth: 260 },
  colTitle:       { color: '#9ca3af', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 },
  gracefulBtn:    { marginTop: 12, width: '100%', padding: '8px', background: '#374151', color: '#d1d5db', border: '1px solid #4b5563', borderRadius: 6, cursor: 'pointer', fontSize: 13 },
};

// Landing page
const lp = {
  page:         { paddingTop: 8 },
  hero:         { display: 'flex', gap: 32, alignItems: 'flex-start', marginBottom: 32, flexWrap: 'wrap' },
  heroLeft:     { flex: '1 1 380px', minWidth: 0 },
  heroRight:    { flex: '0 0 360px', minWidth: 280 },
  badge:        { fontSize: 10, fontWeight: 700, color: '#60a5fa', letterSpacing: 2, textTransform: 'uppercase', marginBottom: 12 },
  heroTitle:    { fontSize: 38, fontWeight: 900, color: '#f9fafb', lineHeight: 1.15, margin: '0 0 16px', letterSpacing: '-0.5px' },
  heroDesc:     { fontSize: 14, color: '#9ca3af', lineHeight: 1.7, margin: '0 0 20px', maxWidth: 460 },
  features:     { display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 28 },
  pill:         { fontSize: 11, color: '#34d399', background: '#052e16', border: '1px solid #14532d', borderRadius: 20, padding: '4px 10px', fontWeight: 600 },
  launchBtn:    { display: 'inline-block', padding: '13px 28px', background: 'linear-gradient(135deg, #1d4ed8, #3b82f6)', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 700, fontSize: 15, boxShadow: '0 4px 20px rgba(59,130,246,0.35)', letterSpacing: '0.3px' },

  anatomyCard:  { background: '#0f172a', border: '1px solid #1e3a5f', borderRadius: 12, padding: '20px 20px 16px' },
  anatomyLabel: { fontSize: 10, fontWeight: 700, color: '#6b7280', letterSpacing: 2, textTransform: 'uppercase', marginBottom: 12 },
  anatomyFooter:{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 10 },
  aFootItem:    { display: 'flex', alignItems: 'flex-start', gap: 10 },
  aFootDot:     { width: 8, height: 8, borderRadius: '50%', marginTop: 4, flexShrink: 0 },
  aFootTitle:   { fontSize: 12, fontWeight: 600, color: '#e5e7eb' },
  aFootSub:     { fontSize: 11, color: '#6b7280' },

  statsBar:     { display: 'flex', gap: 1, marginBottom: 28, background: '#111827', borderRadius: 10, overflow: 'hidden', border: '1px solid #1f2937' },
  histSection:  { background: '#0b0f18', border: '1px solid #1f2937', borderRadius: 10, padding: '16px 18px' },
  sectionLabel: { fontSize: 10, fontWeight: 700, color: '#6b7280', letterSpacing: 2, textTransform: 'uppercase', marginBottom: 10 },
  noHistory:    { color: '#4b5563', textAlign: 'center', padding: '48px 24px', fontSize: 14 },
};

// Anatomy diagram
const an = {
  wrap:     { padding: '4px 0 8px' },
  tagRow:   { display: 'flex', justifyContent: 'center', gap: 20, marginTop: 6 },
  tagRed:   { fontSize: 11, color: '#fca5a5' },
  tagGreen: { fontSize: 11, color: '#86efac' },
};

// Stat card
const sc = {
  card:  { flex: 1, padding: '16px 20px', textAlign: 'center', borderRight: '1px solid #1f2937' },
  value: { fontSize: 22, fontWeight: 800, marginBottom: 4 },
  label: { fontSize: 11, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1 },
  sub:   { fontSize: 10, color: '#4b5563', marginTop: 2 },
};

// History rows
const hr = {
  header:  { display: 'flex', gap: 12, padding: '0 12px 8px', borderBottom: '1px solid #1f2937', marginBottom: 4 },
  hId:     { flex: '0 0 80px', fontSize: 10, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1 },
  hStatus: { flex: '0 0 100px', fontSize: 10, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1 },
  hDate:   { flex: '0 0 70px', fontSize: 10, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1 },
  hPnl:    { flex: '0 0 120px', fontSize: 10, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1 },
  hReason: { flex: 1, fontSize: 10, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1 },
  row:     { display: 'flex', gap: 12, alignItems: 'center', padding: '9px 12px', borderRadius: 6, cursor: 'pointer', border: '1px solid', transition: 'background 0.15s' },
  id:      { flex: '0 0 80px', fontFamily: 'monospace', fontSize: 12, color: '#6b7280' },
  status:  { flex: '0 0 100px', fontSize: 12, fontWeight: 700 },
  date:    { flex: '0 0 70px', fontSize: 12, color: '#6b7280' },
  pnl:     { flex: '0 0 120px', fontFamily: 'monospace', fontSize: 13, fontWeight: 700 },
  reason:  { flex: 1, fontSize: 11, color: '#4b5563' },
};
