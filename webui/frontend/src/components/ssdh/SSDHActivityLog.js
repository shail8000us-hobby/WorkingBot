/**
 * SSDHActivityLog — Last N activity events for a session, polled every 15s
 */
import React, { useEffect, useState, useCallback } from 'react';

const SEV_COLOR = { info: '#6b7280', success: '#22c55e', warning: '#f59e0b', error: '#ef4444', critical: '#ef4444' };

function fmtTime(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch { return ''; }
}

export default function SSDHActivityLog({ sessionId }) {
  const [entries, setEntries] = useState([]);

  const fetch_ = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res  = await fetch(`/api/ssdh/sessions/${sessionId}/activity?limit=15`);
      const data = await res.json();
      setEntries(data.activities || []);
    } catch {}
  }, [sessionId]);

  useEffect(() => {
    fetch_();
    const t = setInterval(fetch_, 15000);
    return () => clearInterval(t);
  }, [fetch_]);

  return (
    <div style={{ background: '#111827', borderRadius: 8, padding: '14px 16px' }}>
      <div style={{ color: '#9ca3af', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>
        Activity Log
      </div>
      {entries.length === 0 ? (
        <div style={{ color: '#4b5563', fontSize: 12, textAlign: 'center', padding: '8px 0' }}>No events yet</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5, maxHeight: 220, overflowY: 'auto' }}>
          {entries.map((e, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 12 }}>
              <span style={{ color: '#4b5563', fontFamily: 'monospace', whiteSpace: 'nowrap', flexShrink: 0 }}>
                {fmtTime(e.timestamp)}
              </span>
              <span style={{ color: SEV_COLOR[e.severity] || '#6b7280', flexShrink: 0, fontSize: 10, marginTop: 1 }}>●</span>
              <span style={{ color: '#d1d5db', lineHeight: 1.4 }}>{e.message || e.label || e.activity_type}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
