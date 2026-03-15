/**
 * CardBuilder — 6-step wizard for creating / editing Patience scenario cards.
 *
 * Steps:
 *   1. Trigger (price, type, tolerance, sustain)
 *   2. IV Gate (min/max percentile with live IV reference)
 *   3. Legs (direction, option_type, expiry, strike, lots, order_mode, flags)
 *   4. Chain (optional parent card)
 *   5. Review & Arm (GCD preview, card summary)
 *
 * Created: March 14, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import patienceAPI from './patienceService';
import optionsChainAPI from '../optionsChain/services/chainAPI';

// DDMMYYYY → YYYY-MM-DD
function toIsoDate(ddmmyyyy) {
  if (!ddmmyyyy || ddmmyyyy.length !== 8) return '';
  const dd = ddmmyyyy.slice(0, 2);
  const mm = ddmmyyyy.slice(2, 4);
  const yyyy = ddmmyyyy.slice(4, 8);
  return `${yyyy}-${mm}-${dd}`;
}

// YYYY-MM-DD → DDMMYYYY
function toDdmmyyyy(iso) {
  if (!iso || iso.length < 10) return '';
  const [yyyy, mm, dd] = iso.split('-');
  return `${dd}${mm}${yyyy}`;
}

// DDMMYYYY → "15 Mar 2026"
const MONTH_ABBR = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function fmtExpiry(ddmmyyyy) {
  if (!ddmmyyyy || ddmmyyyy.length !== 8) return ddmmyyyy;
  const dd = ddmmyyyy.slice(0, 2);
  const mm = parseInt(ddmmyyyy.slice(2, 4), 10);
  const yyyy = ddmmyyyy.slice(4, 8);
  return `${dd} ${MONTH_ABBR[mm] || mm} ${yyyy}`;
}

const TRIGGER_TYPES = ['CROSS_UP', 'CROSS_DOWN', 'TOUCH', 'SUSTAIN'];
const TRIGGER_LABELS = {
  CROSS_UP: '▲ Cross Up',
  CROSS_DOWN: '▼ Cross Down',
  TOUCH: '◉ Touch',
  SUSTAIN: '⏱ Sustain',
};

// Matches the Options panel exactly
const ORDER_MODE_OPTIONS = [
  { value: 'market_only',      label: '🚀 Market',  desc: 'Immediate market fill' },
  { value: 'maker_first',      label: '🧠 Smart',   desc: 'Limit at mid, fallback to market' },
  { value: 'ssr_standard',     label: '📈 SSR',     desc: 'Smart order routing (standard)' },
  { value: 'ssr_aggressive',   label: '🔥 Aggro',   desc: 'SSR aggressive pricing' },
  { value: 'ssr_conservative', label: '🛡 Safe',    desc: 'SSR conservative pricing' },
];

const OPTION_TYPES = ['CE', 'PE'];
const DIRECTIONS = ['BUY', 'SELL'];

function gcd(a, b) { return b === 0 ? a : gcd(b, a % b); }
function computeGcd(nums) { return nums.reduce((a, b) => gcd(a, b)); }

function GcdPreview({ legs }) {
  if (!legs.length) return null;
  const lots = legs.map(l => parseInt(l.lots) || 0).filter(l => l > 0);
  if (!lots.length) return null;
  const g = computeGcd(lots);
  const rounds = Math.max(...lots) / g;
  const ratios = lots.map(l => l / g);
  return (
    <div style={{ background: '#0f172a', borderRadius: 6, padding: 12, fontSize: 12, marginTop: 10 }}>
      <strong style={{ color: '#a78bfa' }}>GCD Schedule Preview</strong>
      <div style={{ marginTop: 6, color: '#94a3b8' }}>
        GCD = {g} &nbsp;|&nbsp; {rounds} round{rounds !== 1 ? 's' : ''} &nbsp;|&nbsp;
        Per round: [{ratios.join(' : ')}] lots
      </div>
      <div style={{ marginTop: 4, color: '#64748b' }}>
        Max unhedged exposure = 1 round ({ratios.join(', ')} lot{ratios.length > 1 ? 's' : ''})
      </div>
    </div>
  );
}

const inputStyle = {
  background: '#1e293b',
  border: '1px solid #334155',
  borderRadius: 4,
  color: '#e2e8f0',
  padding: '6px 10px',
  fontSize: 13,
  width: '100%',
  boxSizing: 'border-box',
};

const labelStyle = {
  fontSize: 12,
  color: '#94a3b8',
  marginBottom: 4,
  display: 'block',
};

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={labelStyle}>{label}</label>
      {children}
    </div>
  );
}

/**
 * LegEditor — self-contained leg row with live expiry + strike dropdowns.
 * Fetches expirations once on mount, fetches strikes when expiry changes.
 */
function LegEditor({ leg, idx, total, onUpdate, onMove, onRemove }) {
  const [expirations, setExpirations] = useState([]);   // DDMMYYYY strings
  const [strikes, setStrikes] = useState([]);           // numbers
  const [atmStrike, setAtmStrike] = useState(null);
  const [loadingExp, setLoadingExp] = useState(false);
  const [loadingStrikes, setLoadingStrikes] = useState(false);

  // Load expirations once
  useEffect(() => {
    setLoadingExp(true);
    optionsChainAPI.getExpirations('BTC')
      .then(exps => setExpirations(exps))
      .catch(() => {})
      .finally(() => setLoadingExp(false));
  }, []);

  // Load strikes when expiry changes
  useEffect(() => {
    const ddmmyyyy = toDdmmyyyy(leg.expiry_date);
    if (!ddmmyyyy) { setStrikes([]); setAtmStrike(null); return; }
    setLoadingStrikes(true);
    optionsChainAPI.getChainData('BTC', ddmmyyyy)
      .then(data => {
        const rows = data.chain || [];
        setStrikes(rows.map(r => r.strike).filter(Boolean).sort((a, b) => a - b));
        setAtmStrike(data.atm_strike || null);
      })
      .catch(() => { setStrikes([]); setAtmStrike(null); })
      .finally(() => setLoadingStrikes(false));
  }, [leg.expiry_date]);

  const handleExpiryChange = (ddmmyyyy) => {
    onUpdate('expiry_date', toIsoDate(ddmmyyyy));
    onUpdate('strike', ''); // reset strike when expiry changes
  };

  const selectedDdmmyyyy = toDdmmyyyy(leg.expiry_date);

  return (
    <div style={{ background: '#0f172a', borderRadius: 8, padding: 14, marginBottom: 12, border: '1px solid #1e293b' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <strong style={{ color: '#a78bfa', fontSize: 13 }}>Leg {idx + 1}</strong>
        <div style={{ display: 'flex', gap: 4 }}>
          <button onClick={() => onMove(-1)} disabled={idx === 0}
            style={{ padding: '2px 8px', borderRadius: 3, cursor: 'pointer', border: 'none', background: '#1e293b', color: '#94a3b8' }}>↑</button>
          <button onClick={() => onMove(1)} disabled={idx === total - 1}
            style={{ padding: '2px 8px', borderRadius: 3, cursor: 'pointer', border: 'none', background: '#1e293b', color: '#94a3b8' }}>↓</button>
          {total > 1 && (
            <button onClick={onRemove}
              style={{ padding: '2px 8px', borderRadius: 3, cursor: 'pointer', border: 'none', background: '#7f1d1d', color: '#fff' }}>✕</button>
          )}
        </div>
      </div>

      {/* Row 1: Direction / Type / Lots */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
        <Field label="Direction">
          <select style={inputStyle} value={leg.direction} onChange={e => onUpdate('direction', e.target.value)}>
            {DIRECTIONS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </Field>
        <Field label="Option Type">
          <select style={inputStyle} value={leg.option_type} onChange={e => onUpdate('option_type', e.target.value)}>
            {OPTION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </Field>
        <Field label="Lots">
          <input style={inputStyle} type="number" min="1" value={leg.lots}
            onChange={e => onUpdate('lots', e.target.value)} placeholder="e.g. 10" />
        </Field>
      </div>

      {/* Row 2: Expiry dropdown / Order Mode */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <Field label={loadingExp ? 'Expiry (loading…)' : 'Expiry'}>
          <select
            style={inputStyle}
            value={selectedDdmmyyyy}
            onChange={e => handleExpiryChange(e.target.value)}
            disabled={loadingExp}
          >
            <option value="">— select expiry —</option>
            {expirations.map(exp => (
              <option key={exp} value={exp}>{fmtExpiry(exp)}</option>
            ))}
          </select>
        </Field>
        <Field label="Order Mode">
          <select style={inputStyle} value={leg.order_mode} onChange={e => onUpdate('order_mode', e.target.value)}>
            {ORDER_MODE_OPTIONS.map(m => (
              <option key={m.value} value={m.value}>{m.label} — {m.desc}</option>
            ))}
          </select>
        </Field>
      </div>

      {/* Relative strike toggle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <label style={{ fontSize: 12, color: '#94a3b8', whiteSpace: 'nowrap', cursor: 'pointer' }}>
          <input type="checkbox" checked={leg.is_relative_strike}
            onChange={e => onUpdate('is_relative_strike', e.target.checked)} style={{ marginRight: 6 }} />
          Relative Strike (ATM ± offset)
        </label>
      </div>

      {leg.is_relative_strike ? (
        <Field label="ATM Offset (e.g. +3000 above ATM, -3000 OTM put)">
          <input style={inputStyle} type="number" value={leg.relative_offset}
            onChange={e => onUpdate('relative_offset', e.target.value)} placeholder="e.g. 3000 or -3000" />
        </Field>
      ) : (
        <Field label={
          loadingStrikes ? 'Strike (loading…)' :
          atmStrike ? `Strike  (ATM = ${atmStrike?.toLocaleString()})` : 'Strike'
        }>
          <select
            style={inputStyle}
            value={leg.strike}
            onChange={e => onUpdate('strike', e.target.value)}
            disabled={!leg.expiry_date || loadingStrikes}
          >
            <option value="">{leg.expiry_date ? '— select strike —' : '← select expiry first'}</option>
            {strikes.map(s => (
              <option key={s} value={s}>
                {s.toLocaleString()}{s === atmStrike ? ' ★ ATM' : ''}
              </option>
            ))}
          </select>
        </Field>
      )}

      {/* Row 3: SL + flags */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 4 }}>
        <Field label="Local SL (optional, exchange-invisible)">
          <input style={inputStyle} type="number" value={leg.stop_loss}
            onChange={e => onUpdate('stop_loss', e.target.value)} placeholder="e.g. 500 (premium)" />
        </Field>
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', paddingBottom: 4, gap: 6 }}>
          <label style={{ fontSize: 12, color: '#94a3b8', cursor: 'pointer' }}>
            <input type="checkbox" checked={leg.mmm_handoff_eligible}
              onChange={e => onUpdate('mmm_handoff_eligible', e.target.checked)} style={{ marginRight: 6 }} />
            MMM Handoff Eligible
          </label>
          <label style={{ fontSize: 12, color: '#94a3b8', cursor: 'pointer' }}>
            <input type="checkbox" checked={leg.post_only}
              onChange={e => onUpdate('post_only', e.target.checked)} style={{ marginRight: 6 }} />
            Post-Only
          </label>
        </div>
      </div>
    </div>
  );
}

export default function CardBuilder({ initialCard, onSaved, onCancel }) {
  const isEdit = !!initialCard?.card_id;
  const fromTemplate = initialCard?._fromTemplate;

  const [step, setStep] = useState(1);
  const TOTAL_STEPS = 5;

  // Step 1: Trigger
  const [cardName, setCardName] = useState(initialCard?.card_name || '');
  const [triggerPrice, setTriggerPrice] = useState(initialCard?.trigger_price || '');
  const [triggerType, setTriggerType] = useState(
    fromTemplate?.trigger_type || initialCard?.trigger_type || 'CROSS_UP'
  );
  const [tolerance, setTolerance] = useState(
    fromTemplate?.trigger_tolerance ?? initialCard?.trigger_tolerance ?? 50
  );
  const [sustainMins, setSustainMins] = useState(initialCard?.sustain_minutes || '');

  // Step 2: IV Gate
  const [ivMin, setIvMin] = useState(
    fromTemplate?.iv_percentile_min ?? initialCard?.iv_percentile_min ?? ''
  );
  const [ivMax, setIvMax] = useState(
    fromTemplate?.iv_percentile_max ?? initialCard?.iv_percentile_max ?? ''
  );
  const [ivLookback, setIvLookback] = useState(
    fromTemplate?.iv_lookback_days ?? initialCard?.iv_lookback_days ?? 30
  );
  const [currentIV, setCurrentIV] = useState(null);

  // Step 3: Legs
  const defaultLeg = () => ({
    direction: 'SELL',
    option_type: 'CE',
    expiry_date: '',
    strike: '',
    lots: '',
    is_relative_strike: false,
    relative_offset: '',
    order_mode: 'maker_first',
    post_only: true,
    stop_loss: '',
    mmm_handoff_eligible: false,
    leg_order: 0,
  });

  const [legs, setLegs] = useState(() => {
    if (fromTemplate?.legs?.length) return fromTemplate.legs.map((l, i) => ({ ...defaultLeg(), ...l, leg_order: i }));
    if (initialCard?.legs?.length) return initialCard.legs;
    return [defaultLeg()];
  });

  // Step 3: GCD toggle (card-level)
  const [useGcd, setUseGcd] = useState(
    initialCard?.use_gcd !== undefined ? Boolean(initialCard.use_gcd) : true
  );

  // Step 4: Chain
  const [parentCardId, setParentCardId] = useState(initialCard?.parent_card_id || '');
  const [armedCards, setArmedCards] = useState([]);

  // Step 5: Review
  const [armOnSave, setArmOnSave] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Fetch live IV
  useEffect(() => {
    patienceAPI.getIVCurrent().then(r => setCurrentIV(r.data?.percentile)).catch(() => {});
  }, []);

  // Fetch cards for parent chain selection
  useEffect(() => {
    if (step === 4) {
      patienceAPI.getCards('ARMED,WAITING,COMPLETED').then(r => {
        const allCards = r.data?.cards || [];
        setArmedCards(allCards.filter(c => c.card_id !== initialCard?.card_id));
      }).catch(() => {});
    }
  }, [step, initialCard]);

  const updateLeg = (idx, field, value) => {
    setLegs(legs => legs.map((l, i) => i === idx ? { ...l, [field]: value } : l));
  };

  const addLeg = () => setLegs(legs => [...legs, { ...defaultLeg(), leg_order: legs.length }]);
  const removeLeg = (idx) => setLegs(legs => legs.filter((_, i) => i !== idx));
  const moveLeg = (idx, dir) => {
    const newLegs = [...legs];
    const swap = idx + dir;
    if (swap < 0 || swap >= newLegs.length) return;
    [newLegs[idx], newLegs[swap]] = [newLegs[swap], newLegs[idx]];
    setLegs(newLegs.map((l, i) => ({ ...l, leg_order: i })));
  };

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    try {
      const payload = {
        card_name: cardName,
        trigger_price: parseFloat(triggerPrice),
        trigger_type: triggerType,
        trigger_tolerance: parseFloat(tolerance) || 50,
        sustain_minutes: triggerType === 'SUSTAIN' ? parseInt(sustainMins) || null : null,
        iv_percentile_min: ivMin !== '' ? parseFloat(ivMin) : null,
        iv_percentile_max: ivMax !== '' ? parseFloat(ivMax) : null,
        iv_lookback_days: parseInt(ivLookback) || 30,
        parent_card_id: parentCardId || null,
        use_gcd: useGcd,
        legs: legs.map((l, i) => ({
          ...l,
          leg_order: i,
          lots: parseInt(l.lots) || 1,
          strike: l.is_relative_strike ? null : (parseFloat(l.strike) || null),
          relative_offset: l.is_relative_strike ? parseFloat(l.relative_offset) || 0 : null,
          stop_loss: l.stop_loss !== '' ? parseFloat(l.stop_loss) : null,
        })),
        arm: armOnSave,
      };

      if (isEdit) {
        await patienceAPI.updateCard(initialCard.card_id, payload);
        if (armOnSave && initialCard.status === 'DRAFT') {
          await patienceAPI.armCard(initialCard.card_id);
        }
      } else {
        await patienceAPI.createCard(payload);
      }
      onSaved();
    } catch (e) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAsTemplate = async () => {
    try {
      const tplLegs = legs.map(l => ({
        direction: l.direction,
        option_type: l.option_type,
        lots: parseInt(l.lots) || 1,
        order_mode: l.order_mode,
        post_only: l.post_only,
        mmm_handoff_eligible: l.mmm_handoff_eligible,
        is_relative_strike: l.is_relative_strike,
        relative_offset: l.is_relative_strike ? parseFloat(l.relative_offset) || 0 : null,
        stop_loss: l.stop_loss !== '' ? parseFloat(l.stop_loss) : null,
      }));
      const tplName = window.prompt('Template name:', cardName || 'New Template');
      if (!tplName) return;
      await patienceAPI.saveTemplate({
        template_name: tplName,
        trigger_type: triggerType,
        trigger_tolerance: parseFloat(tolerance) || 50,
        iv_percentile_min: ivMin !== '' ? parseFloat(ivMin) : null,
        iv_percentile_max: ivMax !== '' ? parseFloat(ivMax) : null,
        iv_lookback_days: parseInt(ivLookback) || 30,
        legs: tplLegs,
      });
      alert('Template saved!');
    } catch (e) {
      alert('Failed to save template: ' + e.message);
    }
  };

  const stepValid = () => {
    if (step === 1) return cardName.trim() && triggerPrice;
    if (step === 3) return legs.length > 0 && legs.every(l =>
      l.direction && l.option_type && l.expiry_date && l.lots &&
      (l.is_relative_strike || l.strike) // Strike required if not relative
    );
    return true;
  };

  const stepTitle = ['', 'Trigger', 'IV Gate', 'Legs', 'Chain', 'Review & Arm'];

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto', color: '#e2e8f0' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h3 style={{ margin: 0, color: '#a78bfa' }}>
            {isEdit ? 'Edit Card' : 'New Scenario Card'} — Step {step}/{TOTAL_STEPS}: {stepTitle[step]}
          </h3>
          {fromTemplate && <div style={{ fontSize: 11, color: '#64748b' }}>From template: {fromTemplate.template_name}</div>}
        </div>
        <button onClick={onCancel} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 20 }}>✕</button>
      </div>

      {/* Progress bar */}
      <div style={{ height: 4, background: '#1e293b', borderRadius: 2, marginBottom: 24 }}>
        <div style={{ height: '100%', width: `${(step / TOTAL_STEPS) * 100}%`, background: '#7c3aed', borderRadius: 2, transition: 'width 0.3s' }} />
      </div>

      {error && (
        <div style={{ background: '#7f1d1d', borderRadius: 6, padding: 10, marginBottom: 14, fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}

      {/* ── Step 1: Trigger ───────────────────────────────────────── */}
      {step === 1 && (
        <div>
          <Field label="Card Name">
            <input style={inputStyle} value={cardName} onChange={e => setCardName(e.target.value)} placeholder="e.g. Bull swing layer" />
          </Field>
          <Field label="Trigger Price (BTC USD)">
            <input style={inputStyle} type="number" value={triggerPrice} onChange={e => setTriggerPrice(e.target.value)} placeholder="e.g. 72000" />
          </Field>
          <Field label="Trigger Type">
            <div style={{ display: 'flex', gap: 8 }}>
              {TRIGGER_TYPES.map(t => (
                <button key={t} onClick={() => setTriggerType(t)} style={{
                  ...{ padding: '6px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 12, border: 'none', fontWeight: 600 },
                  background: triggerType === t ? '#7c3aed' : '#1e293b',
                  color: triggerType === t ? '#fff' : '#94a3b8',
                }}>
                  {TRIGGER_LABELS[t]}
                </button>
              ))}
            </div>
          </Field>
          {triggerType === 'TOUCH' && (
            <Field label={`Touch Tolerance (± pts, default 50)`}>
              <input style={inputStyle} type="number" value={tolerance} onChange={e => setTolerance(e.target.value)} />
            </Field>
          )}
          {triggerType === 'SUSTAIN' && (
            <Field label="Sustain Duration (minutes)">
              <input style={inputStyle} type="number" value={sustainMins} onChange={e => setSustainMins(e.target.value)} placeholder="e.g. 60" />
            </Field>
          )}
        </div>
      )}

      {/* ── Step 2: IV Gate ───────────────────────────────────────── */}
      {step === 2 && (
        <div>
          {currentIV !== null && (
            <div style={{ background: '#0f172a', borderRadius: 6, padding: 12, marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: '#94a3b8' }}>Current IV Percentile</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: '#a78bfa' }}>{currentIV}%</div>
              <div style={{ fontSize: 11, color: '#64748b' }}>Deribit DVOL 30-day percentile</div>
            </div>
          )}
          <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 16 }}>
            Leave empty for no gate. Debit spreads: set IV Max (enter when IV cheap). Credit spreads: set IV Min (sell when IV expensive).
          </div>
          <Field label="IV Percentile Min (credit: IV must be ≥ this)">
            <input style={inputStyle} type="number" min="0" max="100" value={ivMin} onChange={e => setIvMin(e.target.value)} placeholder="e.g. 60 (sell when IV expensive)" />
          </Field>
          <Field label="IV Percentile Max (debit: IV must be ≤ this)">
            <input style={inputStyle} type="number" min="0" max="100" value={ivMax} onChange={e => setIvMax(e.target.value)} placeholder="e.g. 35 (buy when IV cheap)" />
          </Field>
          <Field label="Lookback Days (for percentile calc)">
            <input style={inputStyle} type="number" value={ivLookback} onChange={e => setIvLookback(e.target.value)} />
          </Field>
        </div>
      )}

      {/* ── Step 3: Legs ─────────────────────────────────────────── */}
      {step === 3 && (
        <div>
          {legs.map((leg, idx) => (
            <LegEditor
              key={leg.leg_id || `leg-${idx}`}
              leg={leg}
              idx={idx}
              total={legs.length}
              onUpdate={(field, value) => updateLeg(idx, field, value)}
              onMove={dir => moveLeg(idx, dir)}
              onRemove={() => removeLeg(idx)}
            />
          ))}

          <button onClick={addLeg} style={{ ...{ padding: '8px 16px', borderRadius: 4, cursor: 'pointer', border: '1px dashed #334155', background: 'transparent', color: '#a78bfa', fontSize: 13, width: '100%' } }}>
            + Add Leg
          </button>

          {/* GCD toggle */}
          <div style={{ background: '#0f172a', borderRadius: 6, padding: '10px 14px', marginTop: 12, display: 'flex', alignItems: 'center', gap: 12, border: '1px solid #1e293b' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: '#e2e8f0', flex: 1 }}>
              <input type="checkbox" checked={useGcd} onChange={e => setUseGcd(e.target.checked)} />
              <span><strong>Use GCD lot-splitting</strong></span>
            </label>
            <span style={{ fontSize: 11, color: '#64748b' }}>
              {useGcd
                ? 'ON — splits rounds proportionally, limits unhedged exposure'
                : 'OFF — executes ALL lots in a single round'}
            </span>
          </div>

          {useGcd
            ? <GcdPreview legs={legs} />
            : (
              <div style={{ background: '#0f172a', borderRadius: 6, padding: 12, fontSize: 12, marginTop: 10, color: '#94a3b8' }}>
                <strong style={{ color: '#f97316' }}>GCD Disabled</strong> — 1 round, full lots placed at once:&nbsp;
                {legs.map((l, i) => `${l.direction} ${l.lots || 0} ${l.option_type}`).join(', ')}
              </div>
            )
          }
        </div>
      )}

      {/* ── Step 4: Chain ─────────────────────────────────────────── */}
      {step === 4 && (
        <div>
          <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 16 }}>
            Optional: this card stays WAITING until the parent card COMPLETES. Leave blank for independent card.
          </div>
          <Field label="Parent Card (optional)">
            <select style={inputStyle} value={parentCardId} onChange={e => setParentCardId(e.target.value)}>
              <option value="">None (independent card)</option>
              {armedCards.map(c => (
                <option key={c.card_id} value={c.card_id}>
                  [{c.status}] {c.card_name}
                </option>
              ))}
            </select>
          </Field>
          {parentCardId && (
            <div style={{ background: '#0f172a', borderRadius: 6, padding: 12, fontSize: 12, color: '#a78bfa' }}>
              ⛓ This card will stay WAITING until [{armedCards.find(c => c.card_id === parentCardId)?.card_name}] COMPLETES.
            </div>
          )}
        </div>
      )}

      {/* ── Step 5: Review & Arm ──────────────────────────────────── */}
      {step === 5 && (
        <div>
          <div style={{ background: '#0f172a', borderRadius: 8, padding: 16, marginBottom: 16 }}>
            <strong style={{ color: '#a78bfa' }}>Card Summary</strong>
            <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 13 }}>
              <div><span style={{ color: '#64748b' }}>Name:</span> {cardName}</div>
              <div><span style={{ color: '#64748b' }}>Trigger:</span> BTC {TRIGGER_LABELS[triggerType]} {parseFloat(triggerPrice)?.toLocaleString()}</div>
              {triggerType === 'TOUCH' && <div><span style={{ color: '#64748b' }}>Tolerance:</span> ±{tolerance} pts</div>}
              {triggerType === 'SUSTAIN' && <div><span style={{ color: '#64748b' }}>Sustain:</span> {sustainMins} min</div>}
              {ivMin && <div><span style={{ color: '#64748b' }}>IV Min:</span> ≥{ivMin}%</div>}
              {ivMax && <div><span style={{ color: '#64748b' }}>IV Max:</span> ≤{ivMax}%</div>}
              {parentCardId && <div><span style={{ color: '#64748b' }}>Chain:</span> WAITING for parent</div>}
            </div>

            <div style={{ marginTop: 14 }}>
              <strong style={{ color: '#a78bfa', fontSize: 12 }}>
                Legs ({legs.length}) &nbsp;·&nbsp;
                <span style={{ color: useGcd ? '#22c55e' : '#f97316' }}>
                  {useGcd ? 'GCD ON' : 'GCD OFF (flat)'}
                </span>
              </strong>
              {legs.map((l, i) => {
                const modeLabel = ORDER_MODE_OPTIONS.find(o => o.value === l.order_mode)?.label || l.order_mode;
                return (
                  <div key={i} style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>
                    {i + 1}. {l.direction} {l.lots} {l.option_type} {l.is_relative_strike ? `ATM${l.relative_offset >= 0 ? '+' : ''}${l.relative_offset}` : l.strike}
                    &nbsp;exp:{l.expiry_date}&nbsp;[{modeLabel}]
                    {l.mmm_handoff_eligible ? ' 🔄MMM' : ''}
                    {l.stop_loss ? ` SL:${l.stop_loss}` : ''}
                  </div>
                );
              })}
            </div>

            {useGcd ? <GcdPreview legs={legs} /> : (
              <div style={{ background: '#1e293b', borderRadius: 4, padding: '8px 12px', fontSize: 11, color: '#f97316', marginTop: 10 }}>
                GCD disabled — 1 round, all lots at once
              </div>
            )}
          </div>

          <Field label="">
            <label style={{ fontSize: 13, color: '#e2e8f0', cursor: 'pointer' }}>
              <input type="checkbox" checked={armOnSave} onChange={e => setArmOnSave(e.target.checked)} style={{ marginRight: 8 }} />
              Arm card immediately after saving
            </label>
          </Field>

          <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
            <button onClick={handleSaveAsTemplate} style={{ padding: '8px 14px', borderRadius: 4, border: '1px solid #334155', background: 'transparent', color: '#a78bfa', cursor: 'pointer', fontSize: 12 }}>
              💾 Save as Template
            </button>
          </div>
        </div>
      )}

      {/* ── Navigation ────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24 }}>
        <button onClick={() => step > 1 ? setStep(s => s - 1) : onCancel()}
          style={{ padding: '8px 20px', borderRadius: 4, border: '1px solid #334155', background: 'transparent', color: '#94a3b8', cursor: 'pointer' }}>
          {step === 1 ? 'Cancel' : '← Back'}
        </button>

        <div style={{ display: 'flex', gap: 10 }}>
          {step < TOTAL_STEPS ? (
            <button
              onClick={() => setStep(s => s + 1)}
              disabled={!stepValid()}
              style={{ padding: '8px 24px', borderRadius: 4, border: 'none', background: stepValid() ? '#7c3aed' : '#374151', color: '#fff', cursor: stepValid() ? 'pointer' : 'default', fontWeight: 600 }}>
              Next →
            </button>
          ) : (
            <button
              onClick={handleSave}
              disabled={saving}
              style={{ padding: '8px 24px', borderRadius: 4, border: 'none', background: saving ? '#374151' : '#7c3aed', color: '#fff', cursor: saving ? 'default' : 'pointer', fontWeight: 600 }}>
              {saving ? 'Saving...' : armOnSave ? '⚡ Save & ARM' : '💾 Save (Draft)'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
