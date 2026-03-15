/**
 * TemplateManager — list, preview, and delete saved card templates.
 * "Use Template" opens a focused quick-fill dialog (name, trigger price,
 * per-leg expiry / strike / lots) and creates the card directly.
 *
 * Created: March 14, 2026
 */

import React, { useState, useEffect } from 'react';
import patienceAPI from './patienceService';
import optionsChainAPI from '../optionsChain/services/chainAPI';

// ── Date helpers (same as CardBuilder) ───────────────────────────────
function toIsoDate(ddmmyyyy) {
  if (!ddmmyyyy || ddmmyyyy.length !== 8) return '';
  const dd = ddmmyyyy.slice(0, 2);
  const mm = ddmmyyyy.slice(2, 4);
  const yyyy = ddmmyyyy.slice(4, 8);
  return `${yyyy}-${mm}-${dd}`;
}
function toDdmmyyyy(iso) {
  if (!iso || iso.length < 10) return '';
  const [yyyy, mm, dd] = iso.split('-');
  return `${dd}${mm}${yyyy}`;
}
const MONTH_ABBR = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function fmtExpiry(ddmmyyyy) {
  if (!ddmmyyyy || ddmmyyyy.length !== 8) return ddmmyyyy;
  const dd = ddmmyyyy.slice(0, 2);
  const mm = parseInt(ddmmyyyy.slice(2, 4), 10);
  const yyyy = ddmmyyyy.slice(4, 8);
  return `${dd} ${MONTH_ABBR[mm] || mm} ${yyyy}`;
}

// ── Shared input styles ───────────────────────────────────────────────
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
const labelStyle = { fontSize: 12, color: '#94a3b8', marginBottom: 4, display: 'block' };

// ── Quick-fill modal ──────────────────────────────────────────────────
function TemplateQuickFillModal({ template, onCancel, onCardCreated }) {
  const legs = template.legs || [];

  const [cardName, setCardName] = useState('');
  const [triggerPrice, setTriggerPrice] = useState('');
  const [armOnSave, setArmOnSave] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Per-leg editable state: expiry_date (ISO), strike, lots + options for dropdowns
  const [legData, setLegData] = useState(() =>
    legs.map(l => ({
      expiry_date: '',
      strike: '',
      lots: l.lots || '',
      expirations: [],
      strikes: [],
      atmStrike: null,
      loadingExp: true,
      loadingStrikes: false,
    }))
  );

  // Load expirations once for all legs (same set)
  useEffect(() => {
    optionsChainAPI.getExpirations('BTC')
      .then(exps => {
        setLegData(prev => prev.map(ld => ({ ...ld, expirations: exps, loadingExp: false })));
      })
      .catch(() => {
        setLegData(prev => prev.map(ld => ({ ...ld, loadingExp: false })));
      });
  }, []);

  const handleExpiryChange = (idx, ddmmyyyy) => {
    const isoDate = toIsoDate(ddmmyyyy);
    setLegData(prev => prev.map((ld, i) =>
      i === idx ? { ...ld, expiry_date: isoDate, strike: '', loadingStrikes: !!ddmmyyyy, strikes: [], atmStrike: null } : ld
    ));
    if (!ddmmyyyy) return;
    optionsChainAPI.getChainData('BTC', ddmmyyyy)
      .then(data => {
        const rows = data.chain || [];
        setLegData(prev => prev.map((ld, i) =>
          i === idx ? {
            ...ld,
            strikes: rows.map(r => r.strike).filter(Boolean).sort((a, b) => a - b),
            atmStrike: data.atm_strike || null,
            loadingStrikes: false,
          } : ld
        ));
      })
      .catch(() => {
        setLegData(prev => prev.map((ld, i) => i === idx ? { ...ld, loadingStrikes: false } : ld));
      });
  };

  const updateLegField = (idx, field, value) =>
    setLegData(prev => prev.map((ld, i) => i === idx ? { ...ld, [field]: value } : ld));

  const isValid = cardName.trim() && triggerPrice &&
    legData.every((ld, i) => {
      const l = legs[i];
      return ld.expiry_date && ld.lots && (l.is_relative_strike || ld.strike);
    });

  const handleCreate = async () => {
    setError(null);
    setSaving(true);
    try {
      const payload = {
        card_name: cardName,
        trigger_price: parseFloat(triggerPrice),
        trigger_type: template.trigger_type || 'CROSS_UP',
        trigger_tolerance: template.trigger_tolerance || 50,
        sustain_minutes: null,
        iv_percentile_min: template.iv_percentile_min ?? null,
        iv_percentile_max: template.iv_percentile_max ?? null,
        iv_lookback_days: template.iv_lookback_days || 30,
        parent_card_id: null,
        use_gcd: true,
        legs: legs.map((l, i) => ({
          direction: l.direction,
          option_type: l.option_type,
          expiry_date: legData[i].expiry_date,
          strike: l.is_relative_strike ? null : (parseFloat(legData[i].strike) || null),
          lots: parseInt(legData[i].lots) || 1,
          is_relative_strike: l.is_relative_strike || false,
          relative_offset: l.is_relative_strike ? (parseFloat(l.relative_offset) || 0) : null,
          order_mode: l.order_mode || 'maker_first',
          post_only: l.post_only !== false,
          stop_loss: l.stop_loss || null,
          mmm_handoff_eligible: l.mmm_handoff_eligible || false,
          leg_order: i,
        })),
        arm: armOnSave,
      };
      await patienceAPI.createCard(payload);
      onCardCreated();
    } catch (e) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: '#0f172a', borderRadius: 12, padding: 24,
        width: 560, maxWidth: '95vw', maxHeight: '90vh', overflowY: 'auto',
        border: '1px solid #334155',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <h3 style={{ margin: 0, color: '#a78bfa' }}>Use Template</h3>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 3 }}>
              {template.template_name} · {template.trigger_type} · {legs.length} leg{legs.length !== 1 ? 's' : ''}
              {template.iv_percentile_max != null ? ` · IV ≤ ${template.iv_percentile_max}%` : ''}
              {template.iv_percentile_min != null ? ` · IV ≥ ${template.iv_percentile_min}%` : ''}
            </div>
          </div>
          <button onClick={onCancel} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 20, lineHeight: 1 }}>✕</button>
        </div>

        {error && (
          <div style={{ background: '#7f1d1d', borderRadius: 6, padding: 10, marginBottom: 14, fontSize: 13 }}>
            ⚠ {error}
          </div>
        )}

        {/* Card-level fields */}
        <div style={{ marginBottom: 12 }}>
          <label style={labelStyle}>Card Name</label>
          <input style={inputStyle} value={cardName} onChange={e => setCardName(e.target.value)} placeholder="e.g. Bull swing layer" autoFocus />
        </div>
        <div style={{ marginBottom: 20 }}>
          <label style={labelStyle}>Trigger Price (BTC USD)</label>
          <input style={inputStyle} type="number" value={triggerPrice} onChange={e => setTriggerPrice(e.target.value)} placeholder="e.g. 72000" />
        </div>

        {/* Per-leg fields */}
        <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Leg Details
        </div>
        {legs.map((leg, i) => {
          const ld = legData[i];
          const selectedDdmmyyyy = toDdmmyyyy(ld.expiry_date);
          const cols = leg.is_relative_strike ? '1fr 1fr' : '1fr 1fr 1fr';
          return (
            <div key={i} style={{ background: '#1a2236', borderRadius: 8, padding: 12, marginBottom: 10, border: '1px solid #1e293b' }}>
              {/* Leg label */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <span style={{ fontSize: 11, color: '#64748b' }}>Leg {i + 1}</span>
                <span style={{ color: leg.direction === 'BUY' ? '#22c55e' : '#ef4444', fontWeight: 700, fontSize: 12 }}>
                  {leg.direction}
                </span>
                <span style={{ fontSize: 12, color: '#e2e8f0' }}>{leg.option_type}</span>
                {leg.is_relative_strike && (
                  <span style={{ fontSize: 11, color: '#a78bfa', background: '#1e293b', padding: '1px 6px', borderRadius: 3 }}>
                    ATM{leg.relative_offset >= 0 ? '+' : ''}{leg.relative_offset}
                  </span>
                )}
                <span style={{ fontSize: 11, color: '#64748b', marginLeft: 'auto' }}>{leg.order_mode || 'maker_first'}</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 8 }}>
                {/* Expiry */}
                <div>
                  <label style={labelStyle}>{ld.loadingExp ? 'Expiry (loading…)' : 'Expiry'}</label>
                  <select
                    style={inputStyle}
                    value={selectedDdmmyyyy}
                    onChange={e => handleExpiryChange(i, e.target.value)}
                    disabled={ld.loadingExp}
                  >
                    <option value="">— select —</option>
                    {ld.expirations.map(exp => (
                      <option key={exp} value={exp}>{fmtExpiry(exp)}</option>
                    ))}
                  </select>
                </div>

                {/* Strike (only for non-relative legs) */}
                {!leg.is_relative_strike && (
                  <div>
                    <label style={labelStyle}>
                      {ld.loadingStrikes ? 'Strike (loading…)' : ld.atmStrike ? `Strike (ATM = ${ld.atmStrike?.toLocaleString()})` : 'Strike'}
                    </label>
                    <select
                      style={inputStyle}
                      value={ld.strike}
                      onChange={e => updateLegField(i, 'strike', e.target.value)}
                      disabled={!ld.expiry_date || ld.loadingStrikes}
                    >
                      <option value="">{ld.expiry_date ? '— select —' : '← pick expiry first'}</option>
                      {ld.strikes.map(s => (
                        <option key={s} value={s}>
                          {s.toLocaleString()}{s === ld.atmStrike ? ' ★ ATM' : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Lots */}
                <div>
                  <label style={labelStyle}>Lots</label>
                  <input
                    style={inputStyle}
                    type="number"
                    min="1"
                    value={ld.lots}
                    onChange={e => updateLegField(i, 'lots', e.target.value)}
                    placeholder="e.g. 10"
                  />
                </div>
              </div>
            </div>
          );
        })}

        {/* Arm checkbox */}
        <div style={{ marginTop: 16, marginBottom: 20 }}>
          <label style={{ fontSize: 13, color: '#e2e8f0', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={armOnSave}
              onChange={e => setArmOnSave(e.target.checked)}
              style={{ marginRight: 8 }}
            />
            Arm card immediately after creating
          </label>
        </div>

        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button
            onClick={onCancel}
            style={{ padding: '8px 20px', borderRadius: 4, border: '1px solid #334155', background: 'transparent', color: '#94a3b8', cursor: 'pointer' }}
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={!isValid || saving}
            style={{
              padding: '8px 24px', borderRadius: 4, border: 'none', fontWeight: 600, color: '#fff',
              background: isValid && !saving ? '#7c3aed' : '#374151',
              cursor: isValid && !saving ? 'pointer' : 'default',
            }}
          >
            {saving ? 'Creating...' : armOnSave ? '⚡ Create & ARM' : '💾 Create (Draft)'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── TemplateManager ───────────────────────────────────────────────────
export default function TemplateManager({ onCardCreated }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [quickFillTemplate, setQuickFillTemplate] = useState(null);

  const fetchTemplates = async () => {
    try {
      const r = await patienceAPI.getTemplates();
      setTemplates(r.data.templates || []);
    } catch (e) { /* silent */ }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchTemplates(); }, []);

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this template?')) return;
    setDeleting(id);
    try {
      await patienceAPI.deleteTemplate(id);
      setTemplates(t => t.filter(x => x.template_id !== id));
    } catch (e) {
      alert('Delete failed: ' + (e.response?.data?.error || e.message));
    } finally { setDeleting(null); }
  };

  const handleCardCreated = () => {
    setQuickFillTemplate(null);
    onCardCreated?.();
  };

  if (loading) return <div style={{ color: '#64748b', padding: 20 }}>Loading templates...</div>;

  return (
    <div style={{ color: '#e2e8f0' }}>
      <h4 style={{ color: '#a78bfa', marginTop: 0 }}>Saved Templates</h4>

      {templates.length === 0 ? (
        <div style={{ color: '#64748b', fontSize: 13 }}>
          No templates saved yet. Create a card and use "Save as Template" on the Review step.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {templates.map(t => (
            <TemplateCard
              key={t.template_id}
              template={t}
              expanded={expanded === t.template_id}
              onToggle={() => setExpanded(expanded === t.template_id ? null : t.template_id)}
              onUse={() => setQuickFillTemplate(t)}
              onDelete={() => handleDelete(t.template_id)}
              deleting={deleting === t.template_id}
            />
          ))}
        </div>
      )}

      {quickFillTemplate && (
        <TemplateQuickFillModal
          template={quickFillTemplate}
          onCancel={() => setQuickFillTemplate(null)}
          onCardCreated={handleCardCreated}
        />
      )}
    </div>
  );
}

// ── TemplateCard ──────────────────────────────────────────────────────
function TemplateCard({ template, expanded, onToggle, onUse, onDelete, deleting }) {
  const legs = template.legs || [];
  const triggerLabel = template.trigger_type || 'Template';

  return (
    <div style={{ border: '1px solid #1e293b', borderRadius: 8, overflow: 'hidden' }}>
      {/* Header */}
      <div
        onClick={onToggle}
        style={{
          background: '#0f172a', padding: '12px 16px', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 12,
        }}
      >
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, color: '#e2e8f0' }}>{template.template_name}</div>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
            {triggerLabel} · {legs.length} leg{legs.length !== 1 ? 's' : ''}
            {template.iv_percentile_max ? ` · IV ≤ ${template.iv_percentile_max}%` : ''}
            {template.iv_percentile_min ? ` · IV ≥ ${template.iv_percentile_min}%` : ''}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={e => { e.stopPropagation(); onUse(); }}
            style={btn('#7c3aed')}
          >
            Use Template
          </button>
          <button
            onClick={e => { e.stopPropagation(); onDelete(); }}
            disabled={deleting}
            style={btn('#ef4444')}
          >
            {deleting ? '...' : 'Delete'}
          </button>
        </div>
        <span style={{ color: '#64748b', fontSize: 12, marginLeft: 4 }}>{expanded ? '▲' : '▼'}</span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{ padding: 16, background: '#0a0f1a' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16, fontSize: 12 }}>
            <Info label="Trigger Type" value={template.trigger_type} />
            {template.trigger_tolerance && <Info label="Tolerance" value={`±$${template.trigger_tolerance}`} />}
            {template.sustain_minutes && <Info label="Sustain" value={`${template.sustain_minutes} min`} />}
            {template.iv_percentile_min != null && <Info label="IV Min" value={`${template.iv_percentile_min}%`} />}
            {template.iv_percentile_max != null && <Info label="IV Max" value={`${template.iv_percentile_max}%`} />}
          </div>

          {legs.length > 0 && (
            <>
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8 }}>Legs</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ color: '#475569', borderBottom: '1px solid #1e293b' }}>
                    {['#', 'Dir', 'Type', 'Strike', 'Expiry', 'Lots', 'Mode', 'MMM?'].map(h => (
                      <th key={h} style={{ padding: '4px 8px', textAlign: 'left', fontWeight: 400 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {legs.map((leg, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #0f172a' }}>
                      <td style={{ padding: '6px 8px', color: '#64748b' }}>{i + 1}</td>
                      <td style={{ padding: '6px 8px', color: leg.direction === 'BUY' ? '#22c55e' : '#ef4444', fontWeight: 700 }}>
                        {leg.direction}
                      </td>
                      <td style={{ padding: '6px 8px' }}>{leg.option_type}</td>
                      <td style={{ padding: '6px 8px' }}>
                        {leg.is_relative_strike
                          ? `ATM${leg.relative_offset >= 0 ? '+' : ''}${leg.relative_offset}`
                          : leg.strike?.toLocaleString()}
                      </td>
                      <td style={{ padding: '6px 8px', color: '#94a3b8' }}>{leg.expiry_date || '—'}</td>
                      <td style={{ padding: '6px 8px' }}>{leg.lots}</td>
                      <td style={{ padding: '6px 8px', color: '#64748b', fontSize: 11 }}>{leg.order_mode}</td>
                      <td style={{ padding: '6px 8px' }}>
                        {leg.mmm_handoff_eligible ? <span style={{ color: '#a78bfa', fontSize: 11 }}>✓</span> : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {template.created_at && (
            <div style={{ fontSize: 10, color: '#475569', marginTop: 12 }}>
              Saved: {template.created_at?.slice(0, 19)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: '#64748b', marginBottom: 2 }}>{label}</div>
      <div style={{ color: '#e2e8f0' }}>{value}</div>
    </div>
  );
}

const btn = (bg) => ({
  padding: '4px 10px', borderRadius: 4, border: 'none',
  background: bg, color: '#fff', cursor: 'pointer',
  fontSize: 11, fontWeight: 600,
});
