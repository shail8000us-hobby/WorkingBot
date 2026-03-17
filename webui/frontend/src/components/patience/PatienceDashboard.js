/**
 * PatienceDashboard — main dashboard for the Patience scenario card engine.
 *
 * Layout:
 *   Header: Live BTC price | IV percentile | Engine status | Bulk controls
 *   Body: Card list (flat) or ChainTreeView (toggle)
 *   Footer: Quick stats
 *
 * Polls /api/patience/status every 3s (visibility-aware).
 * Polls /api/patience/cards every 5s.
 *
 * Created: March 14, 2026
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import patienceAPI from './patienceService';
import CardBuilder from './CardBuilder';
import CardDetail from './CardDetail';
import ChainTreeView from './ChainTreeView';
import IVPanel from './IVPanel';
import PnLDashboard from './PnLDashboard';
import PerformanceHistory from './PerformanceHistory';
import TemplateManager from './TemplateManager';

// ── Status color mapping ──────────────────────────────────────────────
const STATUS_COLORS = {
  DRAFT: '#9ca3af',
  WAITING: '#a78bfa',
  ARMED: '#3b82f6',
  TRIGGERED: '#f97316',
  EXECUTING: '#eab308',
  COMPLETED: '#22c55e',
  PAUSED: '#ef4444',
  CANCELLED: '#6b7280',
};

const STATUS_LABELS = {
  DRAFT: 'Draft',
  WAITING: 'Waiting',
  ARMED: 'Armed',
  TRIGGERED: 'Triggered',
  EXECUTING: 'Executing...',
  COMPLETED: 'Completed',
  PAUSED: 'Paused',
  CANCELLED: 'Cancelled',
};

// ── Compact card tile ────────────────────────────────────────────────
function CardTile({ card, btcPrice, onSelect, onArm, onDisarm, onCancel, onResume }) {
  const status = card.status || 'DRAFT';
  const color = STATUS_COLORS[status] || '#9ca3af';
  const isArmed = status === 'ARMED';
  const isPaused = status === 'PAUSED';
  const isDraft = status === 'DRAFT';
  const isExecuting = ['EXECUTING', 'TRIGGERED'].includes(status);

  const distance = btcPrice && card.trigger_price
    ? (card.trigger_price - btcPrice).toFixed(0)
    : null;

  const hasMmmLegs = card.legs && card.legs.some(l => l.mmm_handoff_eligible);
  const legsCount = card.legs ? card.legs.length : 0;

  return (
    <div
      onClick={() => onSelect(card)}
      style={{
        border: `2px solid ${color}`,
        borderRadius: 8,
        padding: '12px 16px',
        marginBottom: 10,
        cursor: 'pointer',
        background: '#1a1a2e',
        transition: 'opacity 0.2s',
        opacity: status === 'CANCELLED' ? 0.5 : 1,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            background: color,
            color: '#000',
            borderRadius: 4,
            padding: '2px 8px',
            fontSize: 11,
            fontWeight: 700,
          }}>
            {isExecuting ? '⚡ ' : ''}{STATUS_LABELS[status]}
          </span>
          <strong style={{ color: '#e2e8f0', fontSize: 14 }}>{card.card_name}</strong>
          {hasMmmLegs && (
            <span style={{ fontSize: 10, color: '#a78bfa', border: '1px solid #a78bfa', borderRadius: 3, padding: '1px 5px' }}>
              MMM
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {isDraft && (
            <button onClick={e => { e.stopPropagation(); onArm(card.card_id); }}
              style={btnStyle('#3b82f6')}>ARM</button>
          )}
          {isPaused && (
            <button onClick={e => { e.stopPropagation(); onResume(card.card_id); }}
              style={btnStyle('#22c55e')}>RESUME</button>
          )}
          {isArmed && (
            <button onClick={e => { e.stopPropagation(); onDisarm(card.card_id); }}
              style={btnStyle('#6b7280')}>DISARM</button>
          )}
          {!['COMPLETED', 'CANCELLED', 'EXECUTING'].includes(status) && (
            <button onClick={e => { e.stopPropagation(); onCancel(card.card_id); }}
              style={btnStyle('#ef4444')}>✕</button>
          )}
        </div>
      </div>

      <div style={{ marginTop: 8, display: 'flex', gap: 20, flexWrap: 'wrap', fontSize: 12, color: '#94a3b8' }}>
        <span>
          Trigger: BTC {card.trigger_type} {card.trigger_price?.toLocaleString()}
          {card.trigger_tolerance ? ` ±${card.trigger_tolerance}` : ''}
        </span>
        {card.iv_percentile_max && <span>IV ≤ {card.iv_percentile_max}%</span>}
        {card.iv_percentile_min && <span>IV ≥ {card.iv_percentile_min}%</span>}
        <span>{legsCount} leg{legsCount !== 1 ? 's' : ''}</span>
        {card.parent_card_id && <span style={{ color: '#a78bfa' }}>⛓ chained</span>}
      </div>

      {/* Distance gauge — only for ARMED cards with BTC price */}
      {isArmed && distance !== null && (
        <DistanceGauge distance={parseInt(distance)} triggerPrice={card.trigger_price} btcPrice={btcPrice} />
      )}
    </div>
  );
}

const btnStyle = (bg) => ({
  background: bg,
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '3px 10px',
  cursor: 'pointer',
  fontSize: 11,
  fontWeight: 600,
});

// ── Trigger distance gauge ────────────────────────────────────────────
function DistanceGauge({ distance, triggerPrice, btcPrice }) {
  // Show how far BTC is from trigger. Max range: 3000 pts each side.
  const MAX_RANGE = 3000;
  const clampedDist = Math.max(-MAX_RANGE, Math.min(MAX_RANGE, distance));
  // Trigger is above BTC: distance > 0 (bullish arm — wait for price to rise)
  const pct = ((MAX_RANGE + clampedDist) / (2 * MAX_RANGE)) * 100;  // 50% = at trigger
  const proximityPct = 1 - Math.abs(distance) / MAX_RANGE;
  const barColor = proximityPct > 0.8 ? '#ef4444' : proximityPct > 0.6 ? '#f97316' : '#3b82f6';

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#475569', marginBottom: 2 }}>
        <span>BTC ${btcPrice?.toLocaleString()}</span>
        <span style={{ color: Math.abs(distance) < 300 ? '#f97316' : '#64748b', fontWeight: 600 }}>
          {Math.abs(distance) < 300 ? '⚡ ' : ''}{Math.abs(distance).toLocaleString()} pts {distance > 0 ? 'below trigger' : 'above trigger'}
        </span>
        <span>Trigger ${triggerPrice?.toLocaleString()}</span>
      </div>
      <div style={{ height: 4, background: '#1e293b', borderRadius: 2, position: 'relative' }}>
        {/* Current price marker */}
        <div style={{
          position: 'absolute',
          left: `${100 - pct}%`,
          top: -2, width: 8, height: 8,
          background: barColor,
          borderRadius: '50%',
          transform: 'translateX(-50%)',
          transition: 'left 0.5s',
        }} />
        {/* Trigger line */}
        <div style={{
          position: 'absolute',
          left: '50%',
          top: -3, width: 2, height: 10,
          background: '#a78bfa',
          transform: 'translateX(-50%)',
        }} />
        {/* Fill from btc to trigger */}
        <div style={{
          position: 'absolute',
          left: `${Math.min(50, 100 - pct)}%`,
          width: `${Math.abs(50 - (100 - pct))}%`,
          height: '100%',
          background: barColor,
          opacity: 0.3,
          borderRadius: 2,
        }} />
      </div>
    </div>
  );
}

// ── Main dashboard ────────────────────────────────────────────────────
export default function PatienceDashboard() {
  const [status, setStatus] = useState(null);
  const [cards, setCards] = useState([]);
  const [view, setView] = useState('list'); // 'list' | 'tree'
  const [activeTab, setActiveTab] = useState('cards'); // 'cards' | 'iv' | 'pnl' | 'performance' | 'templates'
  const [selectedCard, setSelectedCard] = useState(null);
  const [showBuilder, setShowBuilder] = useState(false);
  const [editCard, setEditCard] = useState(null);
  const [error, setError] = useState(null);

  // Visibility-aware polling
  const visibleRef = useRef(true);
  useEffect(() => {
    const onVisible = () => { visibleRef.current = !document.hidden; };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, []);

  // Poll status
  useEffect(() => {
    const fetchStatus = async () => {
      if (!visibleRef.current) return;
      try {
        const res = await patienceAPI.getStatus();
        setStatus(res.data);
      } catch (e) {
        // silent
      }
    };
    fetchStatus();
    const id = setInterval(fetchStatus, 3000);
    return () => clearInterval(id);
  }, []);

  // Poll cards
  const fetchCards = useCallback(async () => {
    if (!visibleRef.current) return;
    try {
      const res = await patienceAPI.getCards();
      setCards(res.data.cards || []);
    } catch (e) {
      // silent
    }
  }, []);

  useEffect(() => {
    fetchCards();
    const id = setInterval(fetchCards, 5000);
    return () => clearInterval(id);
  }, [fetchCards]);

  // Actions
  const armCard = async (cardId) => {
    try { await patienceAPI.armCard(cardId); fetchCards(); } catch (e) { setError(e.message); }
  };
  const disarmCard = async (cardId) => {
    try { await patienceAPI.disarmCard(cardId); fetchCards(); } catch (e) { setError(e.message); }
  };
  const resumeCard = async (cardId) => {
    try { await patienceAPI.resumeCard(cardId); fetchCards(); } catch (e) { setError(e.message); }
  };
  const cancelCard = async (cardId) => {
    if (!window.confirm('Cancel this card?')) return;
    try { await patienceAPI.cancelCard(cardId); fetchCards(); } catch (e) { setError(e.message); }
  };
  const killSwitch = async () => {
    if (!window.confirm('KILL SWITCH: Cancel all ARMED + WAITING cards?')) return;
    try { const r = await patienceAPI.killSwitch(); alert(`Cancelled ${r.data.cancelled} cards.`); fetchCards(); }
    catch (e) { setError(e.message); }
  };
  const armAll = async () => {
    if (!window.confirm('ARM ALL draft cards? They will start monitoring for triggers.')) return;
    try { const r = await patienceAPI.armAll(); alert(`Armed ${r.data.armed} cards.`); fetchCards(); }
    catch (e) { setError(e.message); }
  };
  const disarmAll = async () => {
    if (!window.confirm('DISARM ALL armed/waiting cards? Monitoring will stop.')) return;
    try { const r = await patienceAPI.disarmAll(); alert(`Disarmed ${r.data.disarmed} cards.`); fetchCards(); }
    catch (e) { setError(e.message); }
  };
  const toggleEngine = async () => {
    try {
      if (status?.running) {
        await patienceAPI.stopEngine();
        setStatus(s => ({ ...s, running: false }));
      } else {
        await patienceAPI.startEngine();
        setStatus(s => ({ ...s, running: true }));
      }
    } catch (e) { setError(e.message); }
  };

  const btcPrice = status?.btc_price;
  const ivPct = null; // populated in IVPanel tab

  // Active / non-terminal cards for list
  const activeCards = cards.filter(c => c.status !== 'CANCELLED');
  const grouped = {};
  activeCards.forEach(c => {
    const g = c.status;
    if (!grouped[g]) grouped[g] = [];
    grouped[g].push(c);
  });

  // ── Card detail view ──────────────────────────────────────────────
  if (selectedCard) {
    return (
      <CardDetail
        card={selectedCard}
        onBack={() => { setSelectedCard(null); fetchCards(); }}
        onRefresh={fetchCards}
        btcPrice={btcPrice}
      />
    );
  }

  // ── Card builder ──────────────────────────────────────────────────
  if (showBuilder) {
    return (
      <CardBuilder
        initialCard={editCard}
        onSaved={() => { setShowBuilder(false); setEditCard(null); fetchCards(); }}
        onCancel={() => { setShowBuilder(false); setEditCard(null); }}
      />
    );
  }

  return (
    <div style={{ padding: '20px', maxWidth: 1200, margin: '0 auto', color: '#e2e8f0' }}>

      {/* ── Header ─────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, color: '#a78bfa' }}>⏳ Patience</h2>
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
            Scenario Card Execution Engine · BTC 30–60 DTE
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          {/* Live BTC price */}
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#22c55e' }}>
              ${btcPrice?.toLocaleString() ?? '—'}
            </div>
            <div style={{ fontSize: 10, color: '#64748b' }}>BTC LIVE</div>
          </div>

          {/* Engine status pill */}
          <button
            onClick={toggleEngine}
            style={{
              padding: '6px 14px',
              borderRadius: 20,
              background: status?.running ? '#166534' : '#7f1d1d',
              fontSize: 12,
              fontWeight: 600,
              color: '#fff',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            {status?.running ? '● ACTIVE (click to stop)' : '○ STOPPED (click to start)'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ background: '#7f1d1d', borderRadius: 6, padding: '8px 16px', marginBottom: 12, fontSize: 13 }}>
          ⚠ {error} <button onClick={() => setError(null)} style={{ marginLeft: 10, cursor: 'pointer' }}>✕</button>
        </div>
      )}

      {/* ── Bulk controls ───────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        <button onClick={() => { setEditCard(null); setShowBuilder(true); }}
          style={{ ...btnStyle('#7c3aed'), padding: '6px 16px', fontSize: 13 }}>
          + New Card
        </button>
        <button onClick={armAll} style={{ ...btnStyle('#3b82f6'), padding: '6px 12px', fontSize: 12 }}>
          ARM ALL
        </button>
        <button onClick={disarmAll} style={{ ...btnStyle('#6b7280'), padding: '6px 12px', fontSize: 12 }}>
          DISARM ALL
        </button>
        <button onClick={killSwitch} style={{ ...btnStyle('#dc2626'), padding: '6px 12px', fontSize: 12 }}>
          🔴 KILL SWITCH
        </button>

        <div style={{ flex: 1 }} />

        {/* View toggle */}
        <div style={{ display: 'flex', gap: 4 }}>
          {['list', 'tree'].map(v => (
            <button key={v} onClick={() => setView(v)} style={{
              ...btnStyle(view === v ? '#7c3aed' : '#374151'),
              padding: '6px 12px', fontSize: 12,
            }}>
              {v === 'list' ? '≡ List' : '🌳 Tree'}
            </button>
          ))}
        </div>
      </div>

      {/* ── Stats bar ────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
        {Object.entries(STATUS_COLORS).map(([st, col]) => {
          const count = (grouped[st] || []).length;
          if (count === 0) return null;
          return (
            <div key={st} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: col }} />
              <span style={{ color: '#94a3b8' }}>{STATUS_LABELS[st]}:</span>
              <strong style={{ color: col }}>{count}</strong>
            </div>
          );
        })}
      </div>

      {/* ── Tab navigation ────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid #334155', paddingBottom: 0 }}>
        {[
          { key: 'cards', label: '📋 Cards' },
          { key: 'pnl', label: '💰 P&L' },
          { key: 'iv', label: '📊 IV' },
          { key: 'performance', label: '🏆 Performance' },
          { key: 'templates', label: '📄 Templates' },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: activeTab === tab.key ? '2px solid #7c3aed' : '2px solid transparent',
              color: activeTab === tab.key ? '#a78bfa' : '#64748b',
              padding: '8px 16px',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: activeTab === tab.key ? 600 : 400,
              marginBottom: -1,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Tab content ───────────────────────────────────────────── */}
      {activeTab === 'cards' && (
        <>
          {view === 'tree' ? (
            <ChainTreeView
              cards={activeCards}
              btcPrice={btcPrice}
              onSelect={setSelectedCard}
              onArm={armCard}
              onDisarm={disarmCard}
              onCancel={cancelCard}
              onResume={resumeCard}
            />
          ) : (
            <>
              {activeCards.length === 0 ? (
                <div style={{ textAlign: 'center', color: '#64748b', padding: 40 }}>
                  No cards yet. Click <strong>+ New Card</strong> to create your first scenario card.
                </div>
              ) : (
                Object.entries({
                  EXECUTING: grouped.EXECUTING || [],
                  TRIGGERED: grouped.TRIGGERED || [],
                  ARMED: grouped.ARMED || [],
                  WAITING: grouped.WAITING || [],
                  PAUSED: grouped.PAUSED || [],
                  COMPLETED: grouped.COMPLETED || [],
                  DRAFT: grouped.DRAFT || [],
                }).map(([st, group]) => group.length > 0 && (
                  <div key={st}>
                    <div style={{ fontSize: 11, color: STATUS_COLORS[st], fontWeight: 700,
                      textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6, marginTop: 12 }}>
                      {STATUS_LABELS[st]} ({group.length})
                    </div>
                    {group.map(card => (
                      <CardTile
                        key={card.card_id}
                        card={card}
                        btcPrice={btcPrice}
                        onSelect={setSelectedCard}
                        onArm={armCard}
                        onDisarm={disarmCard}
                        onCancel={cancelCard}
                        onResume={resumeCard}
                      />
                    ))}
                  </div>
                ))
              )}
            </>
          )}
        </>
      )}

      {activeTab === 'pnl' && <PnLDashboard />}
      {activeTab === 'iv' && <IVPanel />}
      {activeTab === 'performance' && <PerformanceHistory />}
      {activeTab === 'templates' && (
        <TemplateManager
          onCardCreated={() => {
            fetchCards();
            setActiveTab('cards');
          }}
        />
      )}
    </div>
  );
}
