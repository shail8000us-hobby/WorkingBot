/**
 * MMMX pure formatting / time utilities.
 * No React, no imports — safe to use anywhere.
 */

export const fmt = (v, d = 2) => (v == null ? '—' : Number(v).toFixed(d));
export const pnlColor = (v) => (v > 0 ? '#4caf50' : v < 0 ? '#f44336' : 'text.secondary');
export const nowIso = () => new Date().toISOString();

export function parseIsoToMs(value) {
  if (!value) return null;
  const normalized = (value.includes('+') || value.endsWith('Z')) ? value : `${value}Z`;
  const ts = new Date(normalized).getTime();
  return Number.isNaN(ts) ? null : ts;
}

export function heartbeatAgeSec(lastBeatAt) {
  const ts = parseIsoToMs(lastBeatAt);
  if (ts == null) return null;
  const age = Math.floor((Date.now() - ts) / 1000);
  return age >= 0 ? age : null;
}

/** Returns { label, color } for display in chips/text, or null if no timestamp. */
export function heartbeatAge(lastBeatAt) {
  if (!lastBeatAt) return null;
  const ts = lastBeatAt.includes('+') || lastBeatAt.endsWith('Z') ? lastBeatAt : lastBeatAt + 'Z';
  const age = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (isNaN(age) || age < 0) return null;
  const color = age < 120 ? '#4caf50' : age < 600 ? '#ff9800' : '#f44336';
  const label = age < 60 ? `${age}s ago` : age < 3600 ? `${Math.floor(age / 60)}m ago` : `${Math.floor(age / 3600)}h ago`;
  return { label, color };
}

export function formatEta(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return null;
  const sec = Math.max(0, Math.floor(Number(seconds)));
  const mm = Math.floor(sec / 60);
  const ss = sec % 60;
  if (mm >= 60) {
    const hh = Math.floor(mm / 60);
    const rm = mm % 60;
    return `${hh}h ${rm}m`;
  }
  return `${mm}m ${String(ss).padStart(2, '0')}s`;
}

/** Format DDMMYY → human label, e.g. "240426" → "24 Apr 2026" */
export function formatDdmmyy(ddmmyy) {
  if (!ddmmyy || ddmmyy.length !== 6) return ddmmyy;
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const dd = ddmmyy.slice(0, 2);
  const mm = parseInt(ddmmyy.slice(2, 4), 10);
  const yy = ddmmyy.slice(4, 6);
  const month = MONTHS[mm - 1] || '?';
  return `${dd} ${month} 20${yy}`;
}

/** Convert DDMMYYYY (8-digit) → DDMMYY (6-digit). Returns null on invalid input. */
export function ddmmyyyyToDdmmyy(s) {
  if (typeof s !== 'string' || s.length !== 8) return null;
  return s.slice(0, 4) + s.slice(6, 8);
}

/**
 * Compute DTE from session.expiry_date ("DD-MM-YYYY") or expiry_ddmmyy ("DDMMYY").
 * Returns { dte, label, color } or null.
 */
export function computeDTE(expiryDate, expiryDdmmyy) {
  let expiryMs = null;
  if (expiryDate) {
    const p = expiryDate.split('-');
    if (p.length === 3) {
      expiryMs = new Date(`${p[2]}-${p[1]}-${p[0]}T04:30:00Z`).getTime();
    }
  } else if (expiryDdmmyy && expiryDdmmyy.length === 6) {
    const dd = expiryDdmmyy.slice(0, 2);
    const mm = expiryDdmmyy.slice(2, 4);
    const yy = expiryDdmmyy.slice(4, 6);
    expiryMs = new Date(`20${yy}-${mm}-${dd}T04:30:00Z`).getTime();
  }
  if (!expiryMs || isNaN(expiryMs)) return null;
  const diffMs = expiryMs - Date.now();
  if (diffMs <= 0) return { dte: 0, label: 'EXPIRED', color: '#f44336' };
  const dte = Math.ceil(diffMs / 86400000);
  const color = dte <= 3 ? '#f44336' : dte <= 7 ? '#ff5722' : dte <= 14 ? '#ff9800' : '#4caf50';
  return { dte, label: `${dte} DTE`, color };
}

/**
 * Compute a display name for a session.
 * e.g. "24 Apr 2026 · #1"
 */
export function sessionDisplayName(session, allSessions) {
  const expiry = session.expiry_ddmmyy;
  if (!expiry || expiry.length !== 6) return 'No expiry · Draft';
  const siblings = [...allSessions]
    .filter(s => s.expiry_ddmmyy === expiry)
    .sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''));
  const idx = siblings.findIndex(s => s.session_id === session.session_id);
  const num = idx >= 0 ? idx + 1 : '?';
  return `${formatDdmmyy(expiry)} · #${num}`;
}

/** Compute upcoming monthly expiry dates — last Friday of each month. */
export function computeUpcomingExpiries(count = 6) {
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const now = Date.now();
  const result = [];
  let d = new Date();
  d.setUTCDate(1);

  while (result.length < count) {
    const lastDay = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0));
    const dow = lastDay.getUTCDay();
    const back = (dow - 5 + 7) % 7;
    const expDate = new Date(lastDay);
    expDate.setUTCDate(lastDay.getUTCDate() - back);
    const expMs = Date.UTC(expDate.getUTCFullYear(), expDate.getUTCMonth(), expDate.getUTCDate(), 4, 30, 0);
    if (expMs > now) {
      const dd = String(expDate.getUTCDate()).padStart(2, '0');
      const mm = String(expDate.getUTCMonth() + 1).padStart(2, '0');
      const yy = String(expDate.getUTCFullYear()).slice(2);
      const dte = Math.ceil((expMs - now) / 86400000);
      result.push({
        ddmmyy: `${dd}${mm}${yy}`,
        label: `${dd} ${MONTHS[expDate.getUTCMonth()]} ${expDate.getUTCFullYear()} (~${dte} DTE)`,
        month: MONTHS[expDate.getUTCMonth()],
      });
    }
    d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1));
  }
  return result;
}

/**
 * Derive whipsaw level label from score, matching backend mmmx_engine.get_level().
 * Thresholds from session params, with safe defaults.
 */
export function deriveWhipsawLevel(score, params) {
  const cooldown = params?.whipsaw_cooldown_score ?? 4;
  const restrict = params?.whipsaw_restrict_score ?? 3;
  const caution  = params?.whipsaw_caution_score  ?? 2;
  if (score >= cooldown) return 'COOLDOWN';
  if (score >= restrict) return 'RESTRICT';
  if (score >= caution)  return 'CAUTION';
  return 'NORMAL';
}
