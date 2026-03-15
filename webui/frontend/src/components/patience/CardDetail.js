/**
 * CardDetail — execution log + positions summary + MMM handoff + inline leg editing.
 *
 * Sections:
 *   1. Card summary + status + action buttons
 *   2. Legs table with bid/ask/mid + inline editing (lots, expiry, mode)
 *   3. Payoff graph at expiry
 *   4. Execution log
 *   5. Card meta info
 *
 * Created: March 14, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import patienceAPI from './patienceService';
import PatiencePayoffGraph from './PatiencePayoffGraph';

const EVENT_COLORS = {
  TRIGGER_HIT: '#3b82f6',
  IV_BLOCKED: '#a78bfa',
  GREEKS_BLOCKED: '#f97316',
  ROUND_START: '#22c55e',
  ROUND_COMPLETE: '#22c55e',
  LEG_FILL: '#22c55e',
  LEG_FAIL: '#ef4444',
  COMPLETE: '#22c55e',
  PAUSE: '#ef4444',
  MMM_HANDOFF: '#a78bfa',
  SL_ACTIVATED: '#eab308',
};

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

const LEG_STATUS_COLORS = {
  PENDING: '#64748b',
  EXECUTING: '#eab308',
  FILLED: '#22c55e',
  FAILED: '#ef4444',
  CANCELLED: '#6b7280',
  HANDED_TO_MMM: '#a78bfa',
};

const EDITABLE_STATUSES = ['DRAFT', 'ARMED', 'PAUSED'];

const ORDER_MODE_OPTIONS = [
  { value: 'market_only',      label: '🚀 Market' },
  { value: 'maker_first',      label: '🧠 Smart' },
  { value: 'ssr_standard',     label: '📈 SSR' },
  { value: 'ssr_aggressive',   label: '🔥 Aggro' },
  { value: 'ssr_conservative', label: '🛡 Safe' },
];
const modeLabel = (v) => ORDER_MODE_OPTIONS.find(o => o.value === v)?.label || v;

export default function CardDetail({ card: initialCard, onBack, onRefresh }) {
  const [card, setCard] = useState(initialCard);
  const [log, setLog] = useState([]);
  const [loading, setLoading] = useState(false);
  const [prices, setPrices] = useState({});
  const [pricesLoading, setPricesLoading] = useState(false);
  const [editingLeg, setEditingLeg] = useState(null);
  const [editValues, setEditValues] = useState({});
  const [chainStrikes, setChainStrikes] = useState([]);
  const [strikesLoading, setStrikesLoading] = useState(false);
  const [lastPricesAt, setLastPricesAt] = useState(null);

  const cardId = card.card_id;
  const isExecuting = ['EXECUTING', 'TRIGGERED'].includes(card.status);
  const canEditLegs = EDITABLE_STATUSES.includes(card.status);

  // ── Fetch helpers ───────────────────────────────────────────────
  const fetchCard = useCallback(async () => {
    try {
      const r = await patienceAPI.getCard(cardId);
      setCard(r.data.card);
    } catch (e) { /* silent */ }
  }, [cardId]);

  const fetchLog = useCallback(async () => {
    try {
      const r = await patienceAPI.getLog(cardId);
      setLog(r.data.events || []);
    } catch (e) { /* silent */ }
  }, [cardId]);

  const fetchPrices = useCallback(async () => {
    setPricesLoading(true);
    try {
      const r = await patienceAPI.getPrices(cardId);
      const list = r.data.prices || [];
      // Index by leg_id for fast lookup
      const map = {};
      list.forEach(p => { map[p.leg_id] = p; });
      setPrices(map);
      setLastPricesAt(new Date());
    } catch (e) {
      console.error('[CardDetail] Failed to fetch prices:', e?.response?.data || e.message);
    } finally {
      setPricesLoading(false);
    }
  }, [cardId]);

  // Convert YYYY-MM-DD → DDMMYYYY for options chain API
  const toApiExpiry = (iso) => {
    const p = iso.split('-');
    return p[2] + p[1] + p[0];
  };

  const fetchChainStrikes = useCallback(async (expiryIso) => {
    if (!expiryIso) return;
    setStrikesLoading(true);
    try {
      const r = await patienceAPI.getChainStrikes(toApiExpiry(expiryIso));
      const chain = r.data.chain || [];
      setChainStrikes(chain.map(row => row.strike).sort((a, b) => a - b));
    } catch (e) {
      console.error('[CardDetail] Failed to fetch strikes:', e.message);
    } finally {
      setStrikesLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCard();
    fetchLog();
    fetchPrices();
  }, [fetchCard, fetchLog, fetchPrices]);

  // Poll while executing
  useEffect(() => {
    if (!isExecuting) return;
    const id = setInterval(() => { fetchCard(); fetchLog(); }, 3000);
    return () => clearInterval(id);
  }, [isExecuting, fetchCard, fetchLog]);

  // Auto-refresh prices every 5s
  useEffect(() => {
    const id = setInterval(fetchPrices, 5000);
    return () => clearInterval(id);
  }, [fetchPrices]);

  // ── Card-level actions ──────────────────────────────────────────
  const handleArm = async () => {
    try { await patienceAPI.armCard(cardId); fetchCard(); } catch (e) { alert(e.message); }
  };
  const handleCancel = async () => {
    if (!window.confirm('Cancel this card?')) return;
    try { await patienceAPI.cancelCard(cardId); fetchCard(); onRefresh?.(); } catch (e) { alert(e.message); }
  };
  const handlePause = async () => {
    try { await patienceAPI.pauseCard(cardId); fetchCard(); } catch (e) { alert(e.message); }
  };
  const handleResume = async () => {
    try { await patienceAPI.resumeCard(cardId); fetchCard(); } catch (e) { alert(e.message); }
  };
  const handleClose = async () => {
    const exitVal = window.prompt('Exit value (total premium received for closing, optional):');
    if (exitVal === null) return;
    try {
      await patienceAPI.closeCard(cardId, { exit_value: exitVal ? parseFloat(exitVal) : 0 });
      onRefresh?.();
      onBack();
    } catch (e) { alert(e.message); }
  };
  const handleExecuteNow = async () => {
    if (!window.confirm('Execute NOW (bypass trigger)? This will queue the card for immediate execution.')) return;
    try {
      await patienceAPI.executeNow(cardId);
      fetchCard();
      alert('Card queued for immediate execution!');
    } catch (e) {
      alert('Execute Now failed: ' + (e.response?.data?.error || e.message));
    }
  };
  const updateCard = async (patch) => {
    try {
      const r = await patienceAPI.updateCard(cardId, patch);
      setCard(r.data.card);
    } catch (e) {
      alert('Update failed: ' + (e.response?.data?.error || e.message));
    }
  };

  const handleHandoff = async (legId) => {
    if (!window.confirm('Hand this leg to MMM for active management? Patience will stop tracking it.')) return;
    setLoading(true);
    try {
      await patienceAPI.handoffLeg(cardId, legId);
      fetchCard();
      fetchLog();
    } catch (e) {
      alert('Handoff failed: ' + (e.response?.data?.error || e.message));
    } finally {
      setLoading(false);
    }
  };

  // ── Inline leg editing ──────────────────────────────────────────
  const startEdit = (leg) => {
    setEditingLeg(leg.leg_id);
    setEditValues({
      lots: leg.lots,
      expiry_date: leg.expiry_date,
      order_mode: leg.order_mode || 'maker_only',
      strike: leg.strike,
    });
    if (!leg.is_relative_strike && leg.expiry_date) {
      fetchChainStrikes(leg.expiry_date);
    }
  };

  const cancelEdit = () => {
    setEditingLeg(null);
    setEditValues({});
  };

  const saveEdit = async (legId) => {
    setLoading(true);
    try {
      const r = await patienceAPI.updateLeg(cardId, legId, editValues);
      setCard(r.data.card);
      setEditingLeg(null);
      setEditValues({});
      fetchPrices(); // refresh prices after edit
    } catch (e) {
      alert('Save failed: ' + (e.response?.data?.error || e.message));
    } finally {
      setLoading(false);
    }
  };

  const legs = card.legs || [];
  const statusColor = STATUS_COLORS[card.status] || '#9ca3af';

  // ── Render ──────────────────────────────────────────────────────
  return (
    <div style={{ padding: 20, maxWidth: 1100, margin: '0 auto', color: '#e2e8f0' }}>
      {/* Back + header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button onClick={onBack} style={{ background: 'none', border: 'none', color: '#a78bfa', cursor: 'pointer', fontSize: 20 }}>←</button>
        <div>
          <h3 style={{ margin: 0, color: '#e2e8f0' }}>{card.card_name}</h3>
          <div style={{ fontSize: 12, color: '#64748b' }}>
            BTC {card.trigger_type} {card.trigger_price?.toLocaleString()} ·
            {card.iv_percentile_max ? ` IV ≤ ${card.iv_percentile_max}%` : ''}
            {card.iv_percentile_min ? ` IV ≥ ${card.iv_percentile_min}%` : ''}
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ padding: '4px 12px', borderRadius: 12, background: statusColor, color: '#000', fontWeight: 700, fontSize: 12 }}>
            {card.status}
          </span>
          {EDITABLE_STATUSES.includes(card.status) && (
            <button onClick={handleExecuteNow} style={actionBtn('#dc2626')}>⚡ EXECUTE NOW</button>
          )}
          {card.status === 'DRAFT' && (
            <button onClick={handleArm} style={actionBtn('#3b82f6')}>ARM</button>
          )}
          {card.status === 'PAUSED' && (
            <button onClick={handleResume} style={actionBtn('#22c55e')}>RESUME</button>
          )}
          {card.status === 'ARMED' && (
            <button onClick={handlePause} style={actionBtn('#6b7280')}>PAUSE</button>
          )}
          {card.status === 'COMPLETED' && (
            <button onClick={handleClose} style={actionBtn('#7c3aed')}>CLOSE CARD</button>
          )}
          {!['COMPLETED', 'CANCELLED'].includes(card.status) && (
            <button onClick={handleCancel} style={actionBtn('#ef4444')}>CANCEL</button>
          )}
        </div>
      </div>

      {/* ── Legs ────────────────────────────────────────────────── */}
      <Section title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%' }}>
          <span>Legs</span>
          {lastPricesAt && (
            <span style={{ fontSize: 10, color: '#475569' }}>
              prices {Math.round((Date.now() - lastPricesAt) / 1000)}s ago
            </span>
          )}
          <button
            onClick={e => { e.stopPropagation(); fetchPrices(); }}
            disabled={pricesLoading}
            style={{ marginLeft: 'auto', padding: '2px 10px', borderRadius: 4, border: '1px solid #334155', background: 'transparent', color: '#a78bfa', cursor: 'pointer', fontSize: 11 }}
          >
            {pricesLoading ? 'Loading...' : '↻ Refresh Prices'}
          </button>
        </div>
      }>
        {legs.length === 0 ? (
          <div style={{ color: '#64748b', fontSize: 13 }}>No legs.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ color: '#64748b', borderBottom: '1px solid #1e293b' }}>
                  {['#', 'Dir', 'Type', 'Strike', 'Expiry', 'Lots', 'Mode', 'Bid', 'Ask', 'Mid', 'Fill @', 'Status', ''].map(h => (
                    <th key={h} style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 400, whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {legs.map((leg, i) => {
                  const legColor = LEG_STATUS_COLORS[leg.status] || '#64748b';
                  const canHandoff = leg.mmm_handoff_eligible && leg.status === 'FILLED';
                  const isHandedOff = leg.status === 'HANDED_TO_MMM';
                  const isEditing = editingLeg === leg.leg_id;
                  const lp = prices[leg.leg_id];
                  const bid = lp?.bid ?? null;
                  const ask = lp?.ask ?? null;
                  const mark = lp?.mark_price ?? null;
                  const mid = (bid != null && ask != null) ? ((bid + ask) / 2) : mark;
                  const priceError = lp?.error;
                  const symbol = lp?.symbol;

                  return (
                    <tr key={leg.leg_id} style={{ borderBottom: '1px solid #0f172a' }}>
                      <td style={cellStyle}>{i + 1}</td>
                      <td style={{ ...cellStyle, color: leg.direction === 'BUY' ? '#22c55e' : '#ef4444', fontWeight: 700 }}>{leg.direction}</td>
                      <td style={cellStyle}>{leg.option_type}</td>
                      {/* ── Strike (editable for non-relative legs) ── */}
                      <td style={cellStyle}>
                        {isEditing && !leg.is_relative_strike ? (
                          <select
                            value={editValues.strike || ''}
                            onChange={e => setEditValues(v => ({ ...v, strike: parseFloat(e.target.value) }))}
                            style={{ ...inputStyle, width: 90 }}
                            disabled={strikesLoading}
                          >
                            {strikesLoading && <option value="">Loading...</option>}
                            {!strikesLoading && editValues.strike && !chainStrikes.includes(editValues.strike) && (
                              <option value={editValues.strike}>{editValues.strike?.toLocaleString()}</option>
                            )}
                            {chainStrikes.map(s => (
                              <option key={s} value={s}>{s.toLocaleString()}</option>
                            ))}
                          </select>
                        ) : (
                          leg.is_relative_strike
                            ? `ATM${leg.relative_offset >= 0 ? '+' : ''}${leg.relative_offset}`
                            : leg.strike?.toLocaleString()
                        )}
                      </td>

                      {/* ── Expiry (editable) ── */}
                      <td style={cellStyle}>
                        {isEditing ? (
                          <input
                            type="date"
                            value={editValues.expiry_date || ''}
                            onChange={e => {
                              setEditValues(v => ({ ...v, expiry_date: e.target.value }));
                              if (!leg.is_relative_strike && e.target.value) {
                                fetchChainStrikes(e.target.value);
                              }
                            }}
                            style={inputStyle}
                          />
                        ) : (
                          <span style={{ color: '#94a3b8' }}>{leg.expiry_date}</span>
                        )}
                      </td>

                      {/* ── Lots (editable) ── */}
                      <td style={cellStyle}>
                        {isEditing ? (
                          <input
                            type="number"
                            min="1"
                            value={editValues.lots || ''}
                            onChange={e => setEditValues(v => ({ ...v, lots: parseInt(e.target.value) || 0 }))}
                            style={{ ...inputStyle, width: 55 }}
                          />
                        ) : (
                          leg.lots
                        )}
                      </td>

                      {/* ── Mode (editable) ── */}
                      <td style={cellStyle}>
                        {isEditing ? (
                          <select
                            value={editValues.order_mode || 'maker_first'}
                            onChange={e => setEditValues(v => ({ ...v, order_mode: e.target.value }))}
                            style={{ ...inputStyle, width: 110 }}
                          >
                            {ORDER_MODE_OPTIONS.map(o => (
                              <option key={o.value} value={o.value}>{o.label}</option>
                            ))}
                          </select>
                        ) : (
                          <span style={{ color: '#64748b', fontSize: 11 }}>{modeLabel(leg.order_mode)}</span>
                        )}
                      </td>

                      {/* ── Bid / Ask / Mid ── */}
                      <td style={{ ...cellStyle, color: '#3b82f6' }} title={symbol || ''}>
                        {pricesLoading && !lp ? '...' : bid != null ? `$${fmtPrice(bid)}` : priceError ? <span style={{ color: '#ef4444', fontSize: 10 }}title={priceError}>err</span> : '—'}
                      </td>
                      <td style={{ ...cellStyle, color: '#f97316' }} title={symbol || ''}>
                        {pricesLoading && !lp ? '...' : ask != null ? `$${fmtPrice(ask)}` : priceError ? <span style={{ color: '#ef4444', fontSize: 10 }} title={priceError}>err</span> : '—'}
                      </td>
                      <td style={{ ...cellStyle, color: '#a78bfa' }} title={mid != null && bid == null ? 'mark price (no bid/ask)' : ''}>
                        {pricesLoading && !lp ? '...' : mid != null ? `$${fmtPrice(mid)}` : priceError ? <span style={{ color: '#ef4444', fontSize: 10 }} title={priceError}>err</span> : '—'}
                      </td>

                      <td style={{ ...cellStyle, color: '#22c55e' }}>
                        {leg.fill_price ? `$${fmtPrice(leg.fill_price)}` : '—'}
                      </td>
                      <td style={cellStyle}>
                        <span style={{ background: legColor, color: '#000', borderRadius: 3, padding: '2px 6px', fontSize: 11, fontWeight: 700 }}>
                          {isHandedOff ? 'MMM' : leg.status}
                        </span>
                      </td>

                      {/* ── Actions column ── */}
                      <td style={{ ...cellStyle, whiteSpace: 'nowrap' }}>
                        {isEditing ? (
                          <>
                            <button onClick={() => saveEdit(leg.leg_id)} disabled={loading}
                              style={{ ...tinyBtn, background: '#22c55e' }}>Save</button>
                            {' '}
                            <button onClick={cancelEdit}
                              style={{ ...tinyBtn, background: '#6b7280' }}>Cancel</button>
                          </>
                        ) : canEditLegs && leg.status === 'PENDING' ? (
                          <button onClick={() => startEdit(leg)}
                            style={{ ...tinyBtn, background: '#334155' }}>Edit</button>
                        ) : null}
                        {' '}
                        {canHandoff && (
                          <button onClick={() => handleHandoff(leg.leg_id)} disabled={loading}
                            style={{ ...tinyBtn, background: '#7c3aed' }}>MMM</button>
                        )}
                        {isHandedOff && <span style={{ fontSize: 10, color: '#a78bfa' }}>Managed</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {/* ── Payoff Graph ─────────────────────────────────────────── */}
      {legs.length > 0 && (
        <Section title="Payoff at Expiry">
          <PatiencePayoffGraph
            legs={legs}
            prices={Object.values(prices)}
            spotPrice={card.trigger_price}
          />
        </Section>
      )}

      {/* ── Execution log ────────────────────────────────────────── */}
      <Section title={`Execution Log (${log.length} events)`}>
        {log.length === 0 ? (
          <div style={{ color: '#64748b', fontSize: 13 }}>No events yet.</div>
        ) : (
          <div style={{ maxHeight: 400, overflowY: 'auto' }}>
            {[...log].reverse().map(event => (
              <div key={event.id} style={{ display: 'flex', gap: 12, padding: '8px 0', borderBottom: '1px solid #0f172a', fontSize: 12 }}>
                <div style={{ color: '#475569', whiteSpace: 'nowrap', minWidth: 145 }}>
                  {event.created_at?.slice(0, 19).replace('T', ' ')}
                </div>
                <div style={{
                  color: EVENT_COLORS[event.event_type] || '#94a3b8',
                  fontWeight: 700, whiteSpace: 'nowrap', minWidth: 120,
                }}>
                  {event.event_type}
                </div>
                <div style={{ color: '#94a3b8', flex: 1 }}>{event.message}</div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* ── Meta info ────────────────────────────────────────────── */}
      <Section title="Card Info">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, fontSize: 12, color: '#94a3b8' }}>
          <div><span style={{ color: '#64748b' }}>Card ID:</span><br />{card.card_id?.slice(0, 8)}...</div>
          <div><span style={{ color: '#64748b' }}>Created:</span><br />{card.created_at?.slice(0, 19)}</div>
          {card.triggered_at && <div><span style={{ color: '#64748b' }}>Triggered:</span><br />{card.triggered_at?.slice(0, 19)}</div>}
          {card.completed_at && <div><span style={{ color: '#64748b' }}>Completed:</span><br />{card.completed_at?.slice(0, 19)}</div>}
          {card.group_id && <div><span style={{ color: '#64748b' }}>Group:</span><br />{card.group_id}</div>}
          {card.parent_card_id && <div><span style={{ color: '#64748b' }}>Parent:</span><br />{card.parent_card_id?.slice(0, 8)}...</div>}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#64748b' }}>GCD Lot-Sizing:</span>
            {canEditLegs ? (
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={!!card.use_gcd}
                  onChange={e => updateCard({ use_gcd: e.target.checked ? 1 : 0 })}
                  style={{ accentColor: '#a78bfa', width: 14, height: 14 }}
                />
                <span style={{ color: card.use_gcd ? '#a78bfa' : '#64748b', fontSize: 11 }}>
                  {card.use_gcd ? 'ON — proportional rounds' : 'OFF — all lots at once'}
                </span>
              </label>
            ) : (
              <span style={{ color: card.use_gcd ? '#a78bfa' : '#64748b' }}>
                {card.use_gcd ? 'ON' : 'OFF'}
              </span>
            )}
          </div>
        </div>
      </Section>
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────

function fmtPrice(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function Section({ title, children }) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div style={{ marginBottom: 20, border: '1px solid #1e293b', borderRadius: 8, overflow: 'hidden' }}>
      <div
        onClick={() => setCollapsed(c => !c)}
        style={{ background: '#0f172a', padding: '10px 16px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
      >
        <strong style={{ fontSize: 13, color: '#a78bfa', flex: 1 }}>{typeof title === 'string' ? title : title}</strong>
        <span style={{ color: '#64748b', fontSize: 12 }}>{collapsed ? '▼' : '▲'}</span>
      </div>
      {!collapsed && <div style={{ padding: 16 }}>{children}</div>}
    </div>
  );
}

const cellStyle = { padding: '8px', whiteSpace: 'nowrap' };

const inputStyle = {
  background: '#0f172a',
  border: '1px solid #3b82f6',
  borderRadius: 3,
  color: '#e2e8f0',
  padding: '3px 6px',
  fontSize: 12,
  width: 100,
};

const tinyBtn = {
  padding: '3px 8px',
  borderRadius: 3,
  border: 'none',
  color: '#fff',
  cursor: 'pointer',
  fontSize: 11,
  fontWeight: 600,
};

const actionBtn = (bg) => ({
  padding: '5px 12px',
  borderRadius: 4,
  border: 'none',
  background: bg,
  color: '#fff',
  cursor: 'pointer',
  fontSize: 12,
  fontWeight: 600,
});
