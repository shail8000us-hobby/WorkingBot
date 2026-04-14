/**
 * PatienceDashboard — redesigned March 2026
 *
 * Layout (Cards tab):
 *   Header strip: BTC · IV percentile · engine status · bulk controls
 *   Body: [Left 37% swim lanes] | [Right 63% context panel]
 *   Tabs: Cards | Positions | Performance | IV | Templates
 *
 * Swim lanes: Firing (EXECUTING/TRIGGERED) | Watching (ARMED/WAITING) |
 *             Paused | Draft | Archive (COMPLETED, collapsible)
 * Context panel: Portfolio overview (default) or Mini card detail (on select)
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSocket } from '../../hooks/useSocket';
import patienceAPI from './patienceService';
import CardBuilder from './CardBuilder';
import CardDetail from './CardDetail';
import IVPanel from './IVPanel';
import PerformanceHistory from './PerformanceHistory';
import TemplateManager from './TemplateManager';
import PatiencePayoffGraph from './PatiencePayoffGraph';
import { readWarmJSON, setWarmJSON } from '../../utils/dataWarmCache';

// ── Constants ──────────────────────────────────────────────────────────
const STATUS_COLORS = {
  DRAFT:     '#9ca3af',
  WAITING:   '#a78bfa',
  ARMED:     '#3b82f6',
  TRIGGERED: '#f97316',
  EXECUTING: '#eab308',
  COMPLETED: '#22c55e',
  CLOSED:    '#22c55e',
  PAUSED:    '#ef4444',
  CANCELLED: '#6b7280',
};

const STATUS_LABELS = {
  DRAFT:     'Draft',
  WAITING:   'Waiting',
  ARMED:     'Armed',
  TRIGGERED: 'Triggered',
  EXECUTING: 'Executing',
  COMPLETED: 'Completed',
  CLOSED:    'Closed',
  PAUSED:    'Paused',
  CANCELLED: 'Cancelled',
};

const TRIGGER_ICON = { CROSS_UP: '▲', CROSS_DOWN: '▼', TOUCH: '◉', SUSTAIN: '⏱' };

// ── Helpers ────────────────────────────────────────────────────────────
const btn = (bg, extra = {}) => ({
  background: bg, color: '#fff', border: 'none', borderRadius: 5,
  padding: '4px 12px', cursor: 'pointer', fontSize: 11, fontWeight: 600,
  lineHeight: 1.4, ...extra,
});

const pnlColor = v => v == null ? '#94a3b8' : v > 0 ? '#22c55e' : v < 0 ? '#ef4444' : '#94a3b8';
const fmt2 = v => v == null ? '—' : Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const ivBarColor = pct => pct == null ? '#64748b' : pct < 25 ? '#22c55e' : pct < 50 ? '#eab308' : pct < 75 ? '#f97316' : '#ef4444';

// ── Distance Gauge ─────────────────────────────────────────────────────
function DistanceGauge({ distance, triggerPrice, btcPrice }) {
  const MAX = 4000;
  const clamped = Math.max(-MAX, Math.min(MAX, distance));
  // 100–pct: BTC position from left. 50% = at trigger.
  const btcPct = ((MAX + clamped) / (2 * MAX)) * 100;
  const abs = Math.abs(distance);
  const proximity = 1 - abs / MAX;
  const color = proximity > 0.85 ? '#ef4444' : proximity > 0.65 ? '#f97316' : '#3b82f6';
  const urgent = abs < 500;

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 5 }}>
        <span style={{ color: '#64748b' }}>${btcPrice?.toLocaleString()}</span>
        <span style={{ color: urgent ? '#f97316' : '#475569', fontWeight: urgent ? 700 : 400 }}>
          {urgent ? '⚡ ' : ''}{abs.toLocaleString()} pts {distance > 0 ? 'to trigger ↑' : 'past ↓'}
        </span>
        <span style={{ color: '#a78bfa' }}>${triggerPrice?.toLocaleString()}</span>
      </div>
      <div style={{ height: 6, background: '#1e293b', borderRadius: 3, position: 'relative', overflow: 'visible' }}>
        {/* Fill between BTC and trigger */}
        <div style={{
          position: 'absolute',
          left: `${Math.min(50, 100 - btcPct)}%`,
          width: `${Math.abs(50 - (100 - btcPct))}%`,
          height: '100%', background: color, opacity: 0.2, borderRadius: 3,
        }} />
        {/* BTC dot */}
        <div style={{
          position: 'absolute', left: `${100 - btcPct}%`,
          top: -3, width: 12, height: 12, background: color, borderRadius: '50%',
          transform: 'translateX(-50%)', transition: 'left 0.6s',
          boxShadow: urgent ? `0 0 8px ${color}` : 'none',
        }} />
        {/* Trigger line */}
        <div style={{
          position: 'absolute', left: '50%', top: -4,
          width: 2, height: 14, background: '#a78bfa',
          transform: 'translateX(-50%)',
        }} />
      </div>
    </div>
  );
}

// ── Card Tile (redesigned) ─────────────────────────────────────────────
function CardTile({
  card, btcPrice, selected,
  onSelect, onArm, onDisarm, onCancel, onResume, onClone,
  onPause, onClose, onDelete, onExecuteNow, executingRound,
}) {
  const status   = card.status || 'DRAFT';
  const color    = STATUS_COLORS[status] || '#9ca3af';
  const isArmed     = status === 'ARMED';
  const isWaiting   = status === 'WAITING';
  const isTriggered = status === 'TRIGGERED';
  const isPaused    = status === 'PAUSED';
  const isDraft     = status === 'DRAFT';
  const isCompleted = status === 'COMPLETED';
  const isExecuting = ['EXECUTING', 'TRIGGERED'].includes(status);

  const legs     = card.legs || [];
  const hasMmm   = legs.some(l => l.mmm_handoff_eligible);
  const legsSummary = legs.map(l =>
    `${l.direction === 'BUY' ? '+' : '−'}${l.lots}${l.option_type}`
  ).join('  ');

  const expiries = [...new Set(legs.map(l => l.expiry_date).filter(Boolean))];
  const expiryLabel = expiries.length === 1
    ? new Date(expiries[0]).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
    : expiries.length > 1 ? `${expiries.length} expiries` : null;

  const distance = btcPrice && card.trigger_price
    ? Math.round(card.trigger_price - btcPrice) : null;
  const distPct = distance != null && btcPrice
    ? (Math.abs(distance) / btcPrice * 100).toFixed(1) : null;

  return (
    <div
      onClick={() => onSelect(card)}
      style={{
        borderLeft: `3px solid ${color}`,
        borderRadius: '0 8px 8px 0',
        padding: '10px 12px',
        marginBottom: 6,
        cursor: 'pointer',
        background: selected ? '#1a2744' : '#0f172a',
        outline: selected ? `1px solid ${color}55` : 'none',
        outlineOffset: -1,
        transition: 'background 0.15s',
        opacity: status === 'CANCELLED' ? 0.45 : 1,
      }}
    >
      {/* Row 1: status badge · name · actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
          <span style={{
            background: color + '20', color, border: `1px solid ${color}55`,
            borderRadius: 4, padding: '1px 7px', fontSize: 10, fontWeight: 700,
            whiteSpace: 'nowrap', flexShrink: 0,
          }}>
            {isExecuting ? '⚡ ' : ''}{STATUS_LABELS[status]}
          </span>
          <span style={{
            fontWeight: 600, color: '#e2e8f0', fontSize: 13,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {card.card_name}
          </span>
          {hasMmm && (
            <span style={{
              fontSize: 9, color: '#a78bfa', border: '1px solid #a78bfa55',
              borderRadius: 3, padding: '1px 4px', flexShrink: 0,
            }}>MMM</span>
          )}
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 4, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
          {isDraft     && <button onClick={() => onArm(card.card_id)}       style={btn('#3b82f6')}>ARM</button>}
          {isPaused    && <button onClick={() => onResume(card.card_id)}    style={btn('#22c55e')}>RESUME</button>}
          {(isArmed || isWaiting || isTriggered) &&
                          <button onClick={() => onDisarm(card.card_id)}    style={btn('#475569')}>DISARM</button>}
          {(isArmed || isExecuting) &&
                          <button onClick={() => onPause(card.card_id)}     style={btn('#f97316')}>PAUSE</button>}
          {(isDraft || isArmed || isPaused) &&
                          <button onClick={() => onExecuteNow(card.card_id)} style={btn('#dc2626')}>⚡</button>}
          {isCompleted  && <button onClick={() => onClone(card)}            style={btn('#7c3aed')}>↺</button>}
          {(isCompleted || isPaused) &&
                          <button onClick={() => onClose(card.card_id)}     style={btn('#475569')}>CLOSE</button>}
          {!isExecuting && !['CANCELLED', 'CLOSED'].includes(status) &&
                          <button onClick={() => onDelete(card.card_id)}    style={btn('#374151')}>🗑</button>}
        </div>
      </div>

      {/* Row 2: trigger · legs summary · expiry */}
      <div style={{ display: 'flex', gap: 10, marginTop: 6, fontSize: 11, color: '#64748b', flexWrap: 'wrap' }}>
        <span style={{ color: '#94a3b8' }}>
          {TRIGGER_ICON[card.trigger_type] || '?'} ${card.trigger_price?.toLocaleString()}
        </span>
        {distance !== null && (isArmed || isWaiting) && (
          <span style={{ color: Math.abs(distance) < 500 ? '#f97316' : '#475569' }}>
            {Math.abs(distance).toLocaleString()} pts{distPct ? ` (${distPct}%)` : ''}
          </span>
        )}
        {legsSummary && <span style={{ color: '#94a3b8' }}>{legsSummary}</span>}
        {expiryLabel  && <span>{expiryLabel}</span>}
        {card.iv_percentile_max && <span>IV ≤{card.iv_percentile_max}%</span>}
        {card.parent_card_id    && <span style={{ color: '#a78bfa' }}>⛓</span>}
      </div>

      {/* Distance gauge for watching cards */}
      {(isArmed || isWaiting) && distance !== null && btcPrice && (
        <DistanceGauge distance={distance} triggerPrice={card.trigger_price} btcPrice={btcPrice} />
      )}

      {/* Round progress for executing cards */}
      {isExecuting && executingRound?.card_id === card.card_id && executingRound.total_rounds > 1 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#f97316', marginBottom: 2 }}>
            <span>Round {executingRound.round}/{executingRound.total_rounds}</span>
            <span>{Math.round(executingRound.round / executingRound.total_rounds * 100)}%</span>
          </div>
          <div style={{ height: 3, background: '#1e293b', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{
              width: `${executingRound.round / executingRound.total_rounds * 100}%`,
              height: '100%', background: '#f97316', borderRadius: 2, transition: 'width 0.3s',
            }} />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Swim Lane ──────────────────────────────────────────────────────────
function SwimLane({ title, accent, cards, selectedCardId, collapsible = false, defaultCollapsed = false, ...tileProps }) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  if (!cards.length) return null;

  return (
    <div style={{ marginBottom: 4 }}>
      <div
        onClick={() => collapsible && setCollapsed(c => !c)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '6px 12px',
          fontSize: 10, fontWeight: 700, color: accent,
          textTransform: 'uppercase', letterSpacing: 1,
          cursor: collapsible ? 'pointer' : 'default',
          userSelect: 'none',
        }}
      >
        <span style={{ flex: 1 }}>{title} ({cards.length})</span>
        {collapsible && <span style={{ fontSize: 12, color: '#475569' }}>{collapsed ? '▸' : '▾'}</span>}
      </div>
      {!collapsed && cards.map(card => (
        <CardTile
          key={card.card_id}
          card={card}
          selected={card.card_id === selectedCardId}
          {...tileProps}
        />
      ))}
    </div>
  );
}

// ── Portfolio Overview (right panel default) ───────────────────────────
function PortfolioOverview({ btcPrice, ivPct, status, cards, wsEvents }) {
  const [posData, setPosData] = useState(null);
  const posInFlightRef = useRef(false);
  const posPendingRef = useRef(false);

  useEffect(() => {
    const fetch = async () => {
      if (posInFlightRef.current) {
        posPendingRef.current = true;
        return;
      }

      posInFlightRef.current = true;
      try {
        const r = await patienceAPI.getPositions();
        setPosData(r.data);
      } catch {}
      finally {
        posInFlightRef.current = false;
        if (posPendingRef.current) {
          posPendingRef.current = false;
          Promise.resolve().then(() => {
            fetch();
          });
        }
      }
    };
    fetch();
    const id = setInterval(fetch, 12000);
    return () => clearInterval(id);
  }, []);

  const summary = posData?.summary || {};
  const firing    = cards.filter(c => ['EXECUTING', 'TRIGGERED'].includes(c.status));
  const watching  = cards.filter(c => ['ARMED', 'WAITING'].includes(c.status));
  const paused    = cards.filter(c => c.status === 'PAUSED');
  const completed = cards.filter(c => c.status === 'COMPLETED');

  return (
    <div style={{ padding: '20px 24px', color: '#e2e8f0', overflowY: 'auto', height: '100%', boxSizing: 'border-box' }}>
      <div style={{ fontSize: 10, color: '#334155', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 18 }}>
        Portfolio Overview
      </div>

      {/* uPnL hero */}
      <div style={{
        background: '#0f172a', borderRadius: 12, padding: '18px 22px',
        marginBottom: 14, border: '1px solid #1e293b',
      }}>
        <div style={{ fontSize: 10, color: '#475569', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
          Live Unrealized P&L
        </div>
        <div style={{ fontSize: 34, fontWeight: 700, color: pnlColor(summary.total_upnl) }}>
          {summary.total_upnl != null
            ? `${summary.total_upnl >= 0 ? '+' : ''}$${fmt2(summary.total_upnl)}`
            : '—'}
        </div>
        <div style={{ fontSize: 11, color: '#334155', marginTop: 4 }}>
          {summary.live_legs ?? 0} live legs · {summary.total_legs ?? 0} total
        </div>
      </div>

      {/* Greeks row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
        {[
          {
            label: 'Net Δ',
            value: summary.total_delta != null ? Number(summary.total_delta).toFixed(4) : null,
            color: summary.total_delta > 0 ? '#22c55e' : summary.total_delta < 0 ? '#ef4444' : '#94a3b8',
          },
          {
            label: 'Net Θ/day',
            value: summary.total_theta != null ? `$${fmt2(summary.total_theta)}` : null,
            color: '#a78bfa',
          },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ background: '#0f172a', borderRadius: 8, padding: '12px 16px', border: '1px solid #1e293b' }}>
            <div style={{ fontSize: 10, color: '#475569', marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: color || '#94a3b8' }}>{value ?? '—'}</div>
          </div>
        ))}
      </div>

      {/* Card counts */}
      <div style={{ background: '#0f172a', borderRadius: 10, padding: '14px 18px', marginBottom: 16, border: '1px solid #1e293b' }}>
        <div style={{ fontSize: 10, color: '#334155', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 10 }}>
          Card Status
        </div>
        {[
          { label: 'Firing',    count: firing.length,    color: '#eab308', icon: '⚡' },
          { label: 'Watching',  count: watching.length,  color: '#3b82f6', icon: '👁' },
          { label: 'Paused',    count: paused.length,    color: '#ef4444', icon: '⏸' },
          { label: 'Completed', count: completed.length, color: '#22c55e', icon: '✓' },
        ].map(({ label, count, color, icon }) => (
          count > 0 && (
            <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 12, color: '#64748b' }}>{icon} {label}</span>
              <span style={{ fontSize: 15, fontWeight: 700, color }}>{count}</span>
            </div>
          )
        ))}
        {cards.length === 0 && (
          <div style={{ color: '#334155', fontSize: 12, textAlign: 'center' }}>No active cards</div>
        )}
      </div>

      {/* IV */}
      {ivPct != null && (
        <div style={{ background: '#0f172a', borderRadius: 10, padding: '12px 18px', marginBottom: 16, border: '1px solid #1e293b' }}>
          <div style={{ fontSize: 10, color: '#334155', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
            DVOL Percentile
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: ivBarColor(ivPct) }}>{ivPct}th</div>
            <div style={{ flex: 1, height: 6, background: '#1e293b', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: `${ivPct}%`, height: '100%', background: ivBarColor(ivPct), borderRadius: 3 }} />
            </div>
          </div>
        </div>
      )}

      {/* Recent WS events */}
      {wsEvents.length > 0 && (
        <div>
          <div style={{ fontSize: 10, color: '#334155', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
            Recent Events
          </div>
          {[...wsEvents].reverse().slice(0, 6).map((ev, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11, marginBottom: 6, color: '#64748b', alignItems: 'flex-start' }}>
              <span style={{ color: ev.type === 'success' ? '#22c55e' : '#f97316', flexShrink: 0, marginTop: 1 }}>●</span>
              <span>{ev.msg}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Mini Card Detail (right panel on card selection) ───────────────────
function MiniCardDetail({
  card, btcPrice, onClose, onOpenFull, onRefresh,
  onArm, onDisarm, onPause, onResume, onExecuteNow, onClone, onCardClose, onDelete,
}) {
  const [log, setLog]       = useState([]);
  const [prices, setPrices] = useState({});
  const detailInFlightRef = useRef(false);
  const detailPendingRef = useRef(false);

  useEffect(() => {
    if (!card?.card_id) return;
    const fetch = async () => {
      if (detailInFlightRef.current) {
        detailPendingRef.current = true;
        return;
      }

      detailInFlightRef.current = true;
      const [logRes, priceRes] = await Promise.allSettled([
        patienceAPI.getLog(card.card_id),
        patienceAPI.getPrices(card.card_id),
      ]);
      if (logRes.status === 'fulfilled')   setLog(logRes.value.data?.log || []);
      if (priceRes.status === 'fulfilled') {
        const m = {};
        (priceRes.value.data?.prices || []).forEach(p => { m[p.leg_id] = p; });
        setPrices(m);
      }

      detailInFlightRef.current = false;
      if (detailPendingRef.current) {
        detailPendingRef.current = false;
        Promise.resolve().then(() => {
          fetch();
        });
      }
    };
    fetch();
    const id = setInterval(fetch, 8000);
    return () => clearInterval(id);
  }, [card?.card_id]);

  const status      = card.status || 'DRAFT';
  const color       = STATUS_COLORS[status] || '#9ca3af';
  const isArmed     = status === 'ARMED';
  const isWaiting   = status === 'WAITING';
  const isTriggered = status === 'TRIGGERED';
  const isPaused    = status === 'PAUSED';
  const isDraft     = status === 'DRAFT';
  const isCompleted = status === 'COMPLETED';
  const isExecuting = ['EXECUTING', 'TRIGGERED'].includes(status);

  const legs     = card.legs || [];
  const distance = btcPrice && card.trigger_price
    ? Math.round(card.trigger_price - btcPrice) : null;

  const LOG_COLORS = {
    LEG_FILL: '#22c55e', COMPLETE: '#22c55e', ROUND_COMPLETE: '#22c55e',
    LEG_FAIL: '#ef4444', PAUSE: '#f97316', IV_BLOCKED: '#a78bfa',
    MMM_HANDOFF: '#a78bfa', SL_ACTIVATED: '#eab308',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', color: '#e2e8f0' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '16px 20px 12px', borderBottom: '1px solid #1e293b', flexShrink: 0,
      }}>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', color: '#475569', cursor: 'pointer',
          fontSize: 18, padding: '0 4px', lineHeight: 1, flexShrink: 0,
        }}>←</button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontWeight: 700, fontSize: 14, color: '#e2e8f0',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>{card.card_name}</div>
          <div style={{ fontSize: 10, color, marginTop: 2, fontWeight: 600 }}>
            {STATUS_LABELS[status]}
          </div>
        </div>
        <button onClick={onOpenFull} style={{
          background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
          color: '#94a3b8', cursor: 'pointer', fontSize: 11, padding: '5px 12px', flexShrink: 0,
        }}>Full Detail →</button>
      </div>

      {/* Scrollable body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 20px' }}>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
          {isDraft     && <button onClick={() => { onArm(card.card_id); onRefresh(); }}         style={{ ...btn('#3b82f6'), padding: '5px 14px', fontSize: 12 }}>ARM</button>}
          {isPaused    && <button onClick={() => { onResume(card.card_id); onRefresh(); }}      style={{ ...btn('#22c55e'), padding: '5px 14px', fontSize: 12 }}>RESUME</button>}
          {(isArmed || isWaiting || isTriggered) &&
            <button onClick={() => { onDisarm(card.card_id); onRefresh(); }}                    style={{ ...btn('#475569'), padding: '5px 14px', fontSize: 12 }}>DISARM</button>}
          {(isArmed || isExecuting) &&
            <button onClick={() => { onPause(card.card_id); onRefresh(); }}                    style={{ ...btn('#f97316'), padding: '5px 14px', fontSize: 12 }}>PAUSE</button>}
          {(isDraft || isArmed || isPaused) &&
            <button onClick={() => onExecuteNow(card.card_id)}                                style={{ ...btn('#dc2626'), padding: '5px 14px', fontSize: 12 }}>⚡ Now</button>}
          {isCompleted && <button onClick={() => onClone(card)}                                style={{ ...btn('#7c3aed'), padding: '5px 14px', fontSize: 12 }}>↺ Clone</button>}
          {(isCompleted || isPaused) &&
            <button onClick={() => onCardClose(card.card_id)}                                  style={{ ...btn('#475569'), padding: '5px 14px', fontSize: 12 }}>CLOSE</button>}
          {!isExecuting && !['CANCELLED', 'CLOSED'].includes(status) &&
            <button onClick={() => onDelete(card.card_id)}                                     style={{ ...btn('#374151'), padding: '5px 14px', fontSize: 12 }}>🗑 Delete</button>}
        </div>

        {/* Trigger block */}
        <div style={{ background: '#0f172a', borderRadius: 8, padding: '12px 16px', marginBottom: 14, border: '1px solid #1e293b' }}>
          <div style={{ fontSize: 10, color: '#334155', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
            Trigger Condition
          </div>
          <div style={{ fontSize: 13, color: '#94a3b8' }}>
            BTC&nbsp;<span style={{ color: '#a78bfa', fontWeight: 600 }}>{card.trigger_type}</span>&nbsp;
            <span style={{ color: '#e2e8f0', fontWeight: 700 }}>${card.trigger_price?.toLocaleString()}</span>
            {card.trigger_tolerance ? <span style={{ color: '#475569' }}> ±{card.trigger_tolerance}</span> : null}
          </div>
          {(card.iv_percentile_min != null || card.iv_percentile_max != null) && (
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
              IV gate: {card.iv_percentile_min ?? 0}–{card.iv_percentile_max ?? 100}th pct
            </div>
          )}
          {(isArmed || isWaiting) && distance !== null && btcPrice && (
            <DistanceGauge distance={distance} triggerPrice={card.trigger_price} btcPrice={btcPrice} />
          )}
        </div>

        {/* Legs table */}
        {legs.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 10, color: '#334155', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
              Legs
            </div>
            <div style={{ background: '#0f172a', borderRadius: 8, overflow: 'hidden', border: '1px solid #1e293b' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr style={{ color: '#334155', borderBottom: '1px solid #1e293b' }}>
                    {['Dir', 'Type', 'Strike', 'Expiry', 'Lots', 'Fill', 'Mark'].map(h => (
                      <th key={h} style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 400 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {legs.map((leg, i) => {
                    const p = prices[leg.leg_id] || {};
                    const expLabel = leg.expiry_date
                      ? new Date(leg.expiry_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
                      : '—';
                    return (
                      <tr key={leg.leg_id || i} style={{ borderBottom: '1px solid #0a1120', color: '#94a3b8' }}>
                        <td style={{ padding: '7px 8px', color: leg.direction === 'BUY' ? '#22c55e' : '#ef4444', fontWeight: 700 }}>
                          {leg.direction}
                        </td>
                        <td style={{ padding: '7px 8px' }}>{leg.option_type}</td>
                        <td style={{ padding: '7px 8px' }}>{leg.strike ?? '—'}</td>
                        <td style={{ padding: '7px 8px' }}>{expLabel}</td>
                        <td style={{ padding: '7px 8px' }}>{leg.lots}</td>
                        <td style={{ padding: '7px 8px', color: leg.fill_price ? '#22c55e' : '#334155' }}>
                          {leg.fill_price ? `$${Number(leg.fill_price).toFixed(1)}` : '—'}
                        </td>
                        <td style={{ padding: '7px 8px', color: '#a78bfa' }}>
                          {p.mark_price ? `$${Number(p.mark_price).toFixed(1)}` : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Execution log */}
        {log.length > 0 && (
          <div>
            <div style={{ fontSize: 10, color: '#334155', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
              Execution Log
            </div>
            <div style={{ background: '#0f172a', borderRadius: 8, padding: '10px 12px', border: '1px solid #1e293b' }}>
              {[...log].reverse().slice(0, 10).map((entry, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11, marginBottom: 5, alignItems: 'flex-start' }}>
                  <span style={{ color: '#334155', flexShrink: 0, fontSize: 10, marginTop: 1 }}>
                    {entry.created_at
                      ? new Date(entry.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                      : ''}
                  </span>
                  <span style={{ color: LOG_COLORS[entry.event_type] || '#64748b' }}>
                    {entry.message}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────
export default function PatienceDashboard() {
  const [status,       setStatus]       = useState(() => readWarmJSON('/api/patience/status') || null);
  const [cards,        setCards]        = useState(() => readWarmJSON('/api/patience/cards')?.cards || []);
  const [activeTab,    setActiveTab]    = useState('cards');
  const [selectedCard, setSelectedCard] = useState(null);   // shown in right panel
  const [fullDetailCard, setFullDetailCard] = useState(null); // full-page CardDetail
  const [showBuilder,  setShowBuilder]  = useState(false);
  const [editCard,     setEditCard]     = useState(null);
  const [error,        setError]        = useState(null);
  const [showKillModal, setShowKillModal] = useState(false);
  const [executingRound, setExecutingRound] = useState(null);
  const [wsEvents,     setWsEvents]     = useState([]);
  const [ivPct,        setIvPct]        = useState(() => readWarmJSON('/api/patience/iv/current')?.percentile ?? null);
  const socket = useSocket();

  const visibleRef = useRef(true);
  const statusInFlightRef = useRef(false);
  const statusPendingRef = useRef(false);
  const ivInFlightRef = useRef(false);
  const ivPendingRef = useRef(false);
  const cardsInFlightRef = useRef(false);
  const cardsPendingRef = useRef(false);
  const cardsRef = useRef(cards);

  useEffect(() => {
    cardsRef.current = cards;
  }, [cards]);

  useEffect(() => {
    const onVis = () => { visibleRef.current = !document.hidden; };
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, []);

  // Poll status (3s)
  useEffect(() => {
    const fetch = async () => {
      if (!visibleRef.current) return;
      if (statusInFlightRef.current) {
        statusPendingRef.current = true;
        return;
      }

      statusInFlightRef.current = true;
      try {
        const r = await patienceAPI.getStatus();
        setStatus(r.data);
        setWarmJSON('/api/patience/status', r.data, { ttlMs: 10000 });
      } catch {}
      finally {
        statusInFlightRef.current = false;
        if (statusPendingRef.current) {
          statusPendingRef.current = false;
          Promise.resolve().then(() => {
            fetch();
          });
        }
      }
    };
    fetch();
    const id = setInterval(fetch, 3000);
    return () => clearInterval(id);
  }, []);

  // Poll IV (5 min)
  useEffect(() => {
    const fetch = async () => {
      if (ivInFlightRef.current) {
        ivPendingRef.current = true;
        return;
      }

      ivInFlightRef.current = true;
      try {
        const r = await patienceAPI.getIVCurrent();
        setIvPct(r.data?.percentile ?? null);
        setWarmJSON('/api/patience/iv/current', r.data, { ttlMs: 45000 });
      } catch {}
      finally {
        ivInFlightRef.current = false;
        if (ivPendingRef.current) {
          ivPendingRef.current = false;
          Promise.resolve().then(() => {
            fetch();
          });
        }
      }
    };
    fetch();
    const id = setInterval(fetch, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  // Poll cards (5s)
  const fetchCards = useCallback(async () => {
    if (!visibleRef.current) return;
    if (cardsInFlightRef.current) {
      cardsPendingRef.current = true;
      return;
    }

    cardsInFlightRef.current = true;
    try {
      const r = await patienceAPI.getCards();
      setCards(r.data.cards || []);
      setWarmJSON('/api/patience/cards', r.data, { ttlMs: 10000 });
    } catch {}
    finally {
      cardsInFlightRef.current = false;
      if (cardsPendingRef.current) {
        cardsPendingRef.current = false;
        Promise.resolve().then(() => {
          fetchCards();
        });
      }
    }
  }, []);

  useEffect(() => {
    fetchCards();
    const id = setInterval(fetchCards, 5000);
    return () => clearInterval(id);
  }, [fetchCards]);

  // Keep selectedCard in sync with latest cards data
  useEffect(() => {
    if (!selectedCard) return;
    const fresh = cards.find(c => c.card_id === selectedCard.card_id);
    if (fresh) setSelectedCard(fresh);
  }, [cards]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Actions ──────────────────────────────────────────────────────
  const armCard      = async id => { try { await patienceAPI.armCard(id);      fetchCards(); } catch (e) { setError(e.message); } };
  const disarmCard   = async id => { try { await patienceAPI.disarmCard(id);   fetchCards(); } catch (e) { setError(e.message); } };
  const resumeCard   = async id => { try { await patienceAPI.resumeCard(id);   fetchCards(); } catch (e) { setError(e.message); } };
  const pauseCard    = async id => { try { await patienceAPI.pauseCard(id);    fetchCards(); } catch (e) { setError(e.message); } };
  const cancelCard   = async id => {
    if (!window.confirm('Cancel this card?')) return;
    try { await patienceAPI.cancelCard(id); fetchCards(); setSelectedCard(s => s?.card_id === id ? null : s); }
    catch (e) { setError(e.message); }
  };
  const deleteCard   = async id => {
    if (!window.confirm('Permanently delete this card and all its legs?')) return;
    try { await patienceAPI.deleteCard(id); fetchCards(); setSelectedCard(s => s?.card_id === id ? null : s); }
    catch (e) { setError(e.message); }
  };
  const executeNowCard = async id => {
    try {
      const res = await patienceAPI.getStatus();
      if (!res.data?.running) { setError('Engine not running — start it first.'); return; }
    } catch {}
    if (!window.confirm('Execute NOW (bypass trigger)?')) return;
    try { await patienceAPI.executeNow(id); fetchCards(); } catch (e) { setError(e.message); }
  };
  const cloneCard = async card => {
    const now  = new Date();
    const stamp = now.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
      + ' ' + now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
    const base = card.card_name.replace(/\s*\(copy[^)]*\)\s*$/, '').trim();
    const name = window.prompt('Clone name:', `${base} (copy ${stamp})`);
    if (name === null) return;
    const newTrigger = window.prompt('Trigger price (blank = same):', card.trigger_price);
    if (newTrigger === null) return;
    const overrides = { card_name: name || `${base} (copy)` };
    if (newTrigger && !isNaN(parseFloat(newTrigger))) overrides.trigger_price = parseFloat(newTrigger);
    try {
      const r = await patienceAPI.cloneCard(card.card_id, overrides);
      fetchCards();
      setSelectedCard(r.data.card);
    } catch (e) { setError('Clone failed: ' + (e.response?.data?.error || e.message)); }
  };
  const closeCard = id => {
    // Navigate to full CardDetail for the close form
    const card = cards.find(c => c.card_id === id);
    if (card) setFullDetailCard(card);
  };
  const armAll = async () => {
    if (!window.confirm('ARM ALL draft cards?')) return;
    try { const r = await patienceAPI.armAll(); alert(`Armed ${r.data.armed} cards.`); fetchCards(); }
    catch (e) { setError(e.message); }
  };
  const disarmAll = async () => {
    if (!window.confirm('DISARM ALL armed/waiting cards?')) return;
    try { const r = await patienceAPI.disarmAll(); alert(`Disarmed ${r.data.disarmed} cards.`); fetchCards(); }
    catch (e) { setError(e.message); }
  };
  const killSwitch = async () => {
    setShowKillModal(false);
    try {
      const r = await patienceAPI.killSwitch();
      fetchCards();
      addWsEvent('success', `Kill switch: cancelled ${r.data.cancelled ?? 'all'} cards`);
    } catch (e) { setError(e.message); }
  };
  const toggleEngine = async () => {
    try {
      if (status?.running) { await patienceAPI.stopEngine(); setStatus(s => ({ ...s, running: false })); }
      else                  { await patienceAPI.startEngine(); setStatus(s => ({ ...s, running: true })); }
    } catch (e) { setError(e.message); }
  };

  // ── WebSocket ─────────────────────────────────────────────────────
  const addWsEvent = useCallback((type, msg) => {
    setWsEvents(prev => [...prev.slice(-9), { type, msg, at: Date.now() }]);
  }, []);

  useEffect(() => {
    if (!socket) return;
    const handler = payload => {
      if (!payload) return;
      if (payload.event === 'round_complete') {
        setExecutingRound({ card_id: payload.card_id, round: payload.round, total_rounds: payload.total_rounds });
      } else if (payload.event === 'completed') {
        setExecutingRound(null);
        fetchCards();
        const c = cardsRef.current.find(x => x.card_id === payload.card_id);
        addWsEvent('success', `${c?.card_name || 'Card'} execution complete ✅`);
      } else if (payload.event === 'paused') {
        fetchCards();
        const c = cardsRef.current.find(x => x.card_id === payload.card_id);
        addWsEvent('error', `${c?.card_name || 'Card'} PAUSED — ${payload.error || 'unknown'}`);
      }
    };
    socket.on('patience_card_update', handler);
    return () => socket.off('patience_card_update', handler);
  }, [socket, fetchCards, addWsEvent]);

  const btcPrice  = status?.btc_price;
  const allActive = cards.filter(c => !['CANCELLED', 'CLOSED'].includes(c.status));

  // Grouped swim lanes
  const laneGroups = {
    firing:    allActive.filter(c => ['EXECUTING', 'TRIGGERED'].includes(c.status)),
    watching:  allActive.filter(c => ['ARMED', 'WAITING'].includes(c.status)),
    paused:    allActive.filter(c => c.status === 'PAUSED'),
    draft:     allActive.filter(c => c.status === 'DRAFT'),
    completed: allActive.filter(c => c.status === 'COMPLETED'),
  };

  const sharedLaneProps = {
    btcPrice,
    selectedCardId: selectedCard?.card_id,
    onSelect:      card => setSelectedCard(s => s?.card_id === card.card_id ? null : card),
    onArm:         armCard,
    onDisarm:      disarmCard,
    onCancel:      cancelCard,
    onResume:      resumeCard,
    onClone:       cloneCard,
    onPause:       pauseCard,
    onClose:       closeCard,
    onDelete:      deleteCard,
    onExecuteNow:  executeNowCard,
    executingRound,
  };

  // ── Full-page overrides ───────────────────────────────────────────
  if (fullDetailCard) {
    return (
      <CardDetail
        card={fullDetailCard}
        btcPrice={btcPrice}
        onBack={() => { setFullDetailCard(null); fetchCards(); }}
        onRefresh={fetchCards}
      />
    );
  }
  if (showBuilder) {
    return (
      <CardBuilder
        initialCard={editCard}
        onSaved={() => { setShowBuilder(false); setEditCard(null); fetchCards(); }}
        onCancel={() => { setShowBuilder(false); setEditCard(null); }}
      />
    );
  }

  // ── Render ────────────────────────────────────────────────────────
  return (
    <div style={{ padding: '16px 20px', maxWidth: 1400, margin: '0 auto', color: '#e2e8f0' }}>

      {/* Feed paused banner */}
      {status?.feed_paused && (
        <div style={{
          background: '#78350f', border: '1px solid #f97316', borderRadius: 6,
          padding: '8px 16px', marginBottom: 12, fontSize: 12, color: '#fed7aa',
        }}>
          ⚠ BTC price feed paused — monitoring halted.
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div style={{
          background: '#7f1d1d', borderRadius: 6, padding: '8px 16px', marginBottom: 12, fontSize: 13,
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <span>⚠ {error}</span>
          <button onClick={() => setError(null)} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>✕</button>
        </div>
      )}

      {/* ── Header strip ──────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 16, marginBottom: 14,
        padding: '12px 16px', background: '#0f172a', borderRadius: 10,
        border: '1px solid #1e293b', flexWrap: 'wrap',
      }}>
        {/* Title */}
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#a78bfa', lineHeight: 1.2 }}>⏳ Patience</div>
          <div style={{ fontSize: 10, color: '#334155' }}>BTC Scenario Engine</div>
        </div>

        <div style={{ width: 1, height: 32, background: '#1e293b', flexShrink: 0 }} />

        {/* BTC Price */}
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, color: '#22c55e', lineHeight: 1.1 }}>
            ${btcPrice?.toLocaleString() ?? '—'}
          </div>
          <div style={{ fontSize: 9, color: '#334155' }}>BTC LIVE</div>
        </div>

        {/* IV Percentile */}
        {ivPct != null && (
          <>
            <div style={{ width: 1, height: 32, background: '#1e293b', flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: ivBarColor(ivPct) }}>{ivPct}th</div>
              <div style={{ fontSize: 9, color: '#334155' }}>IV PCT</div>
            </div>
          </>
        )}

        {/* Badges */}
        {status?.armed_count > 0 && (
          <div style={{ background: '#172554', border: '1px solid #3b82f6', borderRadius: 12, padding: '3px 10px', fontSize: 11, color: '#60a5fa', fontWeight: 700 }}>
            Armed: {status.armed_count}
          </div>
        )}
        {status?.executing_card_id && (() => {
          const ec = cards.find(c => c.card_id === status.executing_card_id);
          return (
            <div style={{ background: '#1c1400', border: '1px solid #f97316', borderRadius: 12, padding: '3px 12px', fontSize: 11, color: '#f97316', fontWeight: 700 }}>
              ⚡ {ec?.card_name || 'Executing…'}
            </div>
          );
        })()}

        {/* Engine toggle */}
        <div style={{ marginLeft: 'auto' }}>
          <button onClick={toggleEngine} style={{
            padding: '7px 16px', borderRadius: 20, fontSize: 12, fontWeight: 600,
            color: '#fff', border: 'none', cursor: 'pointer',
            background: status?.running ? '#166534' : '#7f1d1d',
          }}>
            {status?.running ? '● ACTIVE (click to stop)' : '○ STOPPED (click to start)'}
          </button>
        </div>
      </div>

      {/* ── Controls row ──────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        <button onClick={() => { setEditCard(null); setShowBuilder(true); }}
          style={{ ...btn('#7c3aed'), padding: '7px 18px', fontSize: 13 }}>+ New Card</button>
        <button onClick={armAll}   style={{ ...btn('#3b82f6'), padding: '7px 14px', fontSize: 12 }}>ARM ALL</button>
        <button onClick={disarmAll} style={{ ...btn('#475569'), padding: '7px 14px', fontSize: 12 }}>DISARM ALL</button>
        <button onClick={() => setShowKillModal(true)} style={{ ...btn('#dc2626'), padding: '7px 14px', fontSize: 12 }}>🔴 KILL SWITCH</button>

        {/* Quick stats */}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 14, alignItems: 'center', fontSize: 12 }}>
          {Object.entries({
            EXECUTING: '#eab308', TRIGGERED: '#f97316',
            ARMED: '#3b82f6', WAITING: '#a78bfa',
            PAUSED: '#ef4444', COMPLETED: '#22c55e',
          }).map(([st, col]) => {
            const count = cards.filter(c => c.status === st).length;
            if (!count) return null;
            return (
              <span key={st} style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#64748b' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: col, display: 'inline-block' }} />
                <strong style={{ color: col }}>{count}</strong> {STATUS_LABELS[st]}
              </span>
            );
          })}
        </div>
      </div>

      {/* ── Tab navigation ────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 0, borderBottom: '1px solid #1e293b' }}>
        {[
          { key: 'cards',       label: '📋 Cards' },
          { key: 'positions',   label: '📊 Positions' },
          { key: 'performance', label: '🏆 Performance' },
          { key: 'iv',          label: '📈 IV' },
          { key: 'templates',   label: '📄 Templates' },
        ].map(t => (
          <button key={t.key} onClick={() => setActiveTab(t.key)} style={{
            background: 'none', border: 'none',
            borderBottom: activeTab === t.key ? '2px solid #7c3aed' : '2px solid transparent',
            color: activeTab === t.key ? '#a78bfa' : '#475569',
            padding: '8px 16px', cursor: 'pointer', fontSize: 13,
            fontWeight: activeTab === t.key ? 600 : 400, marginBottom: -1,
          }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Tab content ───────────────────────────────────────────── */}

      {activeTab === 'cards' && (
        <div style={{
          display: 'flex', gap: 0,
          border: '1px solid #1e293b', borderTop: 'none',
          borderRadius: '0 0 10px 10px', overflow: 'hidden',
          minHeight: 560,
        }}>
          {/* Left: Card workspace */}
          <div style={{
            width: '37%', minWidth: 300,
            borderRight: '1px solid #1e293b',
            overflowY: 'auto', padding: '12px 8px',
            background: '#080e1a',
          }}>
            {allActive.length === 0 ? (
              <div style={{ textAlign: 'center', color: '#334155', padding: '60px 20px', fontSize: 13 }}>
                No cards yet.<br />
                <button onClick={() => setShowBuilder(true)} style={{
                  ...btn('#7c3aed'), marginTop: 14, padding: '7px 18px', fontSize: 12,
                }}>+ New Card</button>
              </div>
            ) : (
              <>
                <SwimLane title="⚡ Firing"    accent="#eab308" cards={laneGroups.firing}    {...sharedLaneProps} />
                <SwimLane title="👁 Watching"  accent="#3b82f6" cards={laneGroups.watching}  {...sharedLaneProps} />
                <SwimLane title="⏸ Paused"    accent="#ef4444" cards={laneGroups.paused}    {...sharedLaneProps} />
                <SwimLane title="📋 Draft"     accent="#64748b" cards={laneGroups.draft}     {...sharedLaneProps} />
                <SwimLane title="✓ Completed"  accent="#22c55e" cards={laneGroups.completed} {...sharedLaneProps}
                  collapsible defaultCollapsed={laneGroups.completed.length > 2} />
              </>
            )}
          </div>

          {/* Right: Context panel */}
          <div style={{ flex: 1, background: '#0a1120', overflowY: 'auto' }}>
            {selectedCard ? (
              <MiniCardDetail
                card={selectedCard}
                btcPrice={btcPrice}
                onClose={() => setSelectedCard(null)}
                onOpenFull={() => setFullDetailCard(selectedCard)}
                onRefresh={fetchCards}
                onArm={armCard}
                onDisarm={disarmCard}
                onPause={pauseCard}
                onResume={resumeCard}
                onExecuteNow={executeNowCard}
                onClone={cloneCard}
                onCardClose={closeCard}
                onDelete={deleteCard}
              />
            ) : (
              <PortfolioOverview
                btcPrice={btcPrice}
                ivPct={ivPct}
                status={status}
                cards={allActive}
                wsEvents={wsEvents}
              />
            )}
          </div>
        </div>
      )}

      {activeTab === 'positions'   && <div style={{ paddingTop: 20 }}><PositionsPanel btcPrice={btcPrice} /></div>}
      {activeTab === 'performance' && <div style={{ paddingTop: 20 }}><PerformanceHistory /></div>}
      {activeTab === 'iv'          && <div style={{ paddingTop: 20 }}><IVPanel /></div>}
      {activeTab === 'templates'   && (
        <div style={{ paddingTop: 20 }}>
          <TemplateManager onCardCreated={() => { fetchCards(); setActiveTab('cards'); }} />
        </div>
      )}

      {/* ── Kill Switch modal ─────────────────────────────────────── */}
      {showKillModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', zIndex: 2000,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{ background: '#0f172a', border: '2px solid #dc2626', borderRadius: 12, padding: 28, maxWidth: 440, width: '90vw' }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#ef4444', marginBottom: 12 }}>🔴 KILL SWITCH</div>
            <p style={{ color: '#94a3b8', fontSize: 14, margin: '0 0 20px' }}>
              This will <strong style={{ color: '#ef4444' }}>cancel all ARMED, WAITING, and TRIGGERED cards</strong> immediately.
              EXECUTING cards in progress will not be affected.
            </p>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowKillModal(false)} style={{
                padding: '8px 20px', borderRadius: 6, border: '1px solid #334155',
                background: 'transparent', color: '#94a3b8', cursor: 'pointer',
              }}>Cancel</button>
              <button onClick={killSwitch} style={{
                padding: '8px 24px', borderRadius: 6, border: 'none',
                background: '#dc2626', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: 14,
              }}>CONFIRM KILL SWITCH</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Positions Panel ────────────────────────────────────────────────────
const pnlColor2 = v => v == null ? '#94a3b8' : v > 0 ? '#22c55e' : v < 0 ? '#ef4444' : '#94a3b8';
const fmt2pos   = v => v == null ? '—' : Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function PositionsPanel({ btcPrice }) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastAt,  setLastAt]  = useState(null);
  const positionsInFlightRef = useRef(false);
  const positionsPendingRef = useRef(false);

  const fetchPositions = useCallback(async () => {
    if (positionsInFlightRef.current) {
      positionsPendingRef.current = true;
      return;
    }

    positionsInFlightRef.current = true;
    try {
      const r = await patienceAPI.getPositions();
      setData(r.data);
      setLastAt(new Date());
    }
    catch {}
    finally {
      setLoading(false);
      positionsInFlightRef.current = false;
      if (positionsPendingRef.current) {
        positionsPendingRef.current = false;
        Promise.resolve().then(() => {
          fetchPositions();
        });
      }
    }
  }, []);

  useEffect(() => {
    fetchPositions();
    const id = setInterval(fetchPositions, 10000);
    return () => clearInterval(id);
  }, [fetchPositions]);

  if (loading) return <div style={{ color: '#64748b', padding: 20 }}>Loading positions...</div>;

  const cards       = data?.cards   || [];
  const summary     = data?.summary || {};
  const hasPositions = cards.length > 0;
  const allLegs     = cards.flatMap(c => c.legs);
  const allPrices   = allLegs.map(l => ({ leg_id: l.leg_id, bid: l.bid, ask: l.ask, mark_price: l.mark_price }));

  const metricTiles = hasPositions ? [
    { label: 'Total Positions', value: summary.total_legs ?? 0,   color: '#94a3b8', sub: `${summary.live_legs ?? 0} live` },
    { label: 'Portfolio uPnL', value: summary.total_upnl != null  ? `${summary.total_upnl >= 0 ? '+' : ''}$${fmt2pos(summary.total_upnl)}` : '—', color: pnlColor2(summary.total_upnl), sub: 'unrealized' },
    { label: 'Net Δ',          value: summary.total_delta != null ? Number(summary.total_delta).toFixed(4) : '—',                              color: summary.total_delta > 0 ? '#22c55e' : summary.total_delta < 0 ? '#ef4444' : '#94a3b8', sub: 'net delta' },
    { label: 'Net Θ/day',      value: summary.total_theta != null ? `$${fmt2pos(summary.total_theta)}` : '—',                                  color: '#a78bfa', sub: 'theta decay' },
  ] : [];

  return (
    <div style={{ color: '#e2e8f0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <h4 style={{ margin: 0, color: '#a78bfa' }}>Consolidated Positions</h4>
        {lastAt && <span style={{ fontSize: 11, color: '#475569' }}>updated {Math.round((Date.now() - lastAt) / 1000)}s ago</span>}
        <button onClick={fetchPositions} style={{
          marginLeft: 'auto', padding: '3px 12px', borderRadius: 4,
          border: '1px solid #334155', background: 'transparent', color: '#a78bfa', cursor: 'pointer', fontSize: 11,
        }}>↻ Refresh</button>
      </div>

      {hasPositions && (
        <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
          {metricTiles.map(m => (
            <div key={m.label} style={{ background: '#0f172a', borderRadius: 8, padding: '12px 16px', flex: 1, minWidth: 130 }}>
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 3 }}>{m.label}</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: m.color }}>{m.value}</div>
              {m.sub && <div style={{ fontSize: 10, color: '#475569', marginTop: 2 }}>{m.sub}</div>}
            </div>
          ))}
        </div>
      )}

      {!hasPositions ? (
        <div style={{ color: '#64748b', fontSize: 13, padding: 32, textAlign: 'center', border: '1px dashed #1e293b', borderRadius: 8 }}>
          No filled Patience legs found. Execute a card first.
        </div>
      ) : (
        <>
          {cards.map(card => (
            <div key={card.card_id} style={{ marginBottom: 16, border: '1px solid #1e293b', borderRadius: 8, overflow: 'hidden' }}>
              <div style={{ background: '#0f172a', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
                <strong style={{ color: '#e2e8f0', fontSize: 14 }}>{card.card_name}</strong>
                <span style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase' }}>{card.status}</span>
                <span style={{ fontSize: 12, color: '#64748b' }}>{card.live_legs}/{card.total_legs} live</span>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 20, alignItems: 'center' }}>
                  {card.card_delta != null && (
                    <span style={{ fontSize: 12, color: card.card_delta > 0 ? '#22c55e' : card.card_delta < 0 ? '#ef4444' : '#64748b' }}>
                      Δ {Number(card.card_delta).toFixed(4)}
                    </span>
                  )}
                  <span style={{ fontSize: 13, color: pnlColor2(card.card_upnl), fontWeight: 700 }}>
                    uPnL: {card.card_upnl >= 0 ? '+' : ''}${fmt2pos(card.card_upnl)}
                  </span>
                  {card.card_theta !== 0 && (
                    <span style={{ fontSize: 12, color: card.card_theta < 0 ? '#22c55e' : '#ef4444' }}>
                      Θ {card.card_theta >= 0 ? '+' : ''}${fmt2pos(card.card_theta)}/day
                    </span>
                  )}
                </div>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ color: '#64748b', borderBottom: '1px solid #1e293b', background: '#0a1120' }}>
                      {['Symbol', 'Dir', 'Lots', 'Strike', 'Fill @', 'Bid', 'Ask', 'Mark', 'uPnL', 'Θ/day', 'Δ', 'Status'].map(h => (
                        <th key={h} style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 400, whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {card.legs.map(leg => (
                      <tr key={leg.leg_id} style={{ borderBottom: '1px solid #0f172a' }}>
                        <td style={{ padding: '8px 10px', fontFamily: 'monospace', color: leg.is_live ? '#a78bfa' : '#475569', fontSize: 11 }}>
                          {leg.symbol}
                          {leg.expiry_warning?.is_expiring_soon && <span style={{ marginLeft: 4, color: '#f97316', fontSize: 10 }}>⚠ expiring</span>}
                        </td>
                        <td style={{ padding: '8px 10px', color: leg.direction === 'BUY' ? '#22c55e' : '#ef4444', fontWeight: 700 }}>{leg.direction}</td>
                        <td style={{ padding: '8px 10px', color: '#94a3b8' }}>{leg.lots}</td>
                        <td style={{ padding: '8px 10px', color: '#94a3b8' }}>{leg.strike ? `$${leg.strike.toLocaleString()}` : '—'}</td>
                        <td style={{ padding: '8px 10px', color: '#64748b' }}>
                          {leg.fill_price ? `$${fmt2pos(leg.fill_price)}` : <span style={{ color: '#334155', fontSize: 11 }}>awaiting</span>}
                        </td>
                        <td style={{ padding: '8px 10px', color: '#3b82f6' }}>{leg.bid  != null ? `$${fmt2pos(leg.bid)}`  : '—'}</td>
                        <td style={{ padding: '8px 10px', color: '#f97316' }}>{leg.ask  != null ? `$${fmt2pos(leg.ask)}`  : '—'}</td>
                        <td style={{ padding: '8px 10px', color: '#a78bfa' }}>{leg.mark_price != null ? `$${fmt2pos(leg.mark_price)}` : '—'}</td>
                        <td style={{ padding: '8px 10px', fontWeight: 600, color: pnlColor2(leg.unrealized_pnl) }}>
                          {leg.unrealized_pnl != null ? `${leg.unrealized_pnl >= 0 ? '+' : ''}$${fmt2pos(leg.unrealized_pnl)}` : <span style={{ color: '#334155' }}>—</span>}
                        </td>
                        <td style={{ padding: '8px 10px', color: leg.theta < 0 ? '#22c55e' : leg.theta > 0 ? '#ef4444' : '#64748b' }}>
                          {leg.theta != null ? `$${fmt2pos(leg.theta)}` : '—'}
                        </td>
                        <td style={{ padding: '8px 10px', color: '#64748b' }}>{leg.delta != null ? Number(leg.delta).toFixed(4) : '—'}</td>
                        <td style={{ padding: '8px 10px' }}>
                          {leg.leg_status === 'ROUND_FILLED'
                            ? <span style={{ color: '#f97316', fontSize: 11 }}>● round-filled</span>
                            : leg.is_live
                              ? <span style={{ color: '#22c55e', fontSize: 11 }}>● live</span>
                              : <span style={{ color: '#475569', fontSize: 11 }}>○ no mkt data</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}

          {allLegs.some(l => l.strike) && (
            <div style={{ marginTop: 24 }}>
              <div style={{ fontSize: 13, color: '#64748b', marginBottom: 8 }}>
                Combined Portfolio Payoff — {allLegs.length} legs across {cards.length} cards
              </div>
              <PatiencePayoffGraph legs={allLegs} prices={allPrices} spotPrice={btcPrice} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
