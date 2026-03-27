/**
 * OIPanel — Open Interest Aggregator Dashboard Panel
 *
 * Full dashboard with:
 * - Sensibull-style multi-select expiry filter (ExpiryFilter component)
 * - Connection status + last updated indicator
 * - Summary strip: Total Call OI | Total Put OI | PCR | ATM strike | Underlying price
 * - 4 tabs: OI Change | Open Interest | Table | Spike Log
 * - Real-time SocketIO updates on /oi namespace
 * - Stale data banner (>120s without update)
 * - MUI Snackbar toast on spike events
 * - ATM reference line computed from underlying price
 *
 * SocketIO namespace: /oi (isolated from MMM/IC on default '/')
 *
 * Fixes applied (audit 2026-03-27):
 * - D2: oi_update is now metadata-only; rows always fetched via REST for selectedExpiries
 * - D3: atmStrike computed from underlying_price and passed to all charts/table
 * - D4: MUI Snackbar toast fires on oi_spike event
 * - D5: strike count uses Set-based deduplication not length/2
 * - D9: selectedExpiries ref prevents stale-closure race in fetchSnapshot
 *
 * Created: March 27, 2026
 * Revised: March 27, 2026
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Snackbar, Alert } from '@mui/material';
import CollapsibleCard from '../common/CollapsibleCard.tsx';
import ExpiryFilter from './ExpiryFilter';
import OIBarChart from './OIBarChart';
import OIChangeChart from './OIChangeChart';
import OITable from './OITable';
import OISpikeLog from './OISpikeLog';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5555';

const STATUS_COLORS = {
  connected: '#4caf50',
  connecting: '#ff9800',
  disconnected: '#f44336',
};

const TABS = [
  { id: 'change', label: '📉 OI Change' },
  { id: 'absolute', label: '📊 Open Interest' },
  { id: 'table', label: '📋 Table' },
  { id: 'spikes', label: '🔔 Spike Log' },
];

const STALE_THRESHOLD_MS = 120_000; // 2 minutes

function formatNumber(val) {
  if (val == null) return '—';
  if (Math.abs(val) >= 1e6) return `${(val / 1e6).toFixed(2)}M`;
  if (Math.abs(val) >= 1e3) return `${(val / 1e3).toFixed(1)}K`;
  return val.toFixed(0);
}

/**
 * Compute the nearest strike to the underlying spot price.
 * Returns null if data is unavailable.
 */
function computeAtmStrike(underlyingPrice, rows) {
  if (!underlyingPrice || !rows.length) return null;
  const strikes = [...new Set(rows.map(r => r.strike))];
  if (!strikes.length) return null;
  return strikes.reduce((best, s) =>
    Math.abs(s - underlyingPrice) < Math.abs(best - underlyingPrice) ? s : best,
    strikes[0]
  );
}

export default function OIPanel() {
  // Connection state
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [isStale, setIsStale] = useState(false);

  // Data state
  const [rows, setRows] = useState([]);
  const [expiries, setExpiries] = useState([]);          // [{date, is_weekly, days_to_expiry}]
  const [selectedExpiries, setSelectedExpiries] = useState([]);  // string[] of ISO dates
  const [underlyingPrice, setUnderlyingPrice] = useState(0);
  const [summary, setSummary] = useState({ total_call_oi: 0, total_put_oi: 0, pcr: 0, by_expiry: {} });
  const [spikes, setSpikes] = useState([]);
  const [health, setHealth] = useState({});
  const [activeTab, setActiveTab] = useState('change');

  // Spike toast
  const [toastOpen, setToastOpen] = useState(false);
  const [toastSpike, setToastSpike] = useState(null);

  // Refs
  const socketRef = useRef(null);
  const lastUpdateRef = useRef(null);
  const staleTimerRef = useRef(null);
  // Keep selectedExpiries available in SocketIO event closures without recreating them
  const selectedExpiriesRef = useRef(selectedExpiries);
  useEffect(() => { selectedExpiriesRef.current = selectedExpiries; }, [selectedExpiries]);
  // Track in-flight fetch to cancel on rapid changes
  const fetchAbortRef = useRef(null);

  // ------------------------------------------------------------------
  // ATM strike (derived, not state)
  // ------------------------------------------------------------------
  const atmStrike = useMemo(
    () => computeAtmStrike(underlyingPrice, rows),
    [underlyingPrice, rows]
  );

  // ------------------------------------------------------------------
  // Filter rows to selected expiries (client-side)
  // ------------------------------------------------------------------
  const filteredRows = useMemo(() => {
    if (!selectedExpiries.length) return [];
    return rows.filter(r => selectedExpiries.includes(r.expiry));
  }, [rows, selectedExpiries]);

  // ------------------------------------------------------------------
  // Stale data detection
  // ------------------------------------------------------------------
  useEffect(() => {
    staleTimerRef.current = setInterval(() => {
      if (lastUpdateRef.current) {
        const age = Date.now() - lastUpdateRef.current;
        setIsStale(age > STALE_THRESHOLD_MS);
      }
    }, 5000);
    return () => clearInterval(staleTimerRef.current);
  }, []);

  // ------------------------------------------------------------------
  // Fetch historical spikes on mount
  // ------------------------------------------------------------------
  const fetchSpikes = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/oi/spikes?last_n=100`);
      const data = await res.json();
      if (data.spikes) setSpikes(data.spikes);
    } catch (e) {
      console.warn('[OI] Failed to fetch spikes:', e);
    }
  }, []);

  // ------------------------------------------------------------------
  // Fetch snapshot for given expiry list (used after oi_update + on filter change)
  // Uses AbortController to cancel stale requests on rapid selection changes.
  // ------------------------------------------------------------------
  const fetchSnapshot = useCallback(async (expiriesToFetch) => {
    if (!expiriesToFetch || !expiriesToFetch.length) {
      setRows([]);
      setSummary({ total_call_oi: 0, total_put_oi: 0, pcr: 0, by_expiry: {} });
      return;
    }

    // Cancel any in-flight request
    if (fetchAbortRef.current) {
      fetchAbortRef.current.abort();
    }
    const controller = new AbortController();
    fetchAbortRef.current = controller;

    try {
      const params = new URLSearchParams({
        underlying: 'BTC',
        expiries: expiriesToFetch.join(','),
      });
      const res = await fetch(`${API_BASE}/api/oi/snapshot?${params}`, {
        signal: controller.signal,
      });
      const data = await res.json();
      if (data.rows) setRows(data.rows);
      if (data.summary) setSummary(data.summary);
      if (data.underlying_price) setUnderlyingPrice(data.underlying_price);
    } catch (e) {
      if (e.name === 'AbortError') return; // cancelled — ignore
      console.warn('[OI] Failed to fetch snapshot:', e);
    }
  }, []); // stable — no deps that change

  // ------------------------------------------------------------------
  // SocketIO connection
  // ------------------------------------------------------------------
  useEffect(() => {
    let socket = null;

    const connectOI = async () => {
      try {
        const { io } = await import('socket.io-client');
        const baseUrl = window.location.hostname === 'localhost'
          ? 'http://localhost:5555'
          : window.location.origin;

        socket = io(`${baseUrl}/oi`, {
          transports: ['websocket', 'polling'],
          reconnection: true,
          reconnectionDelay: 2000,
          reconnectionAttempts: Infinity,
        });

        socket.on('connect', () => {
          console.log('[OI] Connected to /oi namespace');
          setConnectionStatus('connected');
        });

        socket.on('disconnect', () => {
          console.log('[OI] Disconnected from /oi namespace');
          setConnectionStatus('disconnected');
        });

        socket.on('connect_error', () => {
          setConnectionStatus('disconnected');
        });

        // oi_update is now METADATA ONLY — no rows pushed from server.
        // This fixes D2: server was overwriting user's expiry selection.
        // On each metadata update, we fetch rows for the user's current selectedExpiries.
        socket.on('oi_update', (meta) => {
          const now = Date.now();
          setLastUpdated(new Date(now).toLocaleTimeString('en-IN', {
            hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
          }));
          lastUpdateRef.current = now;
          setIsStale(false);

          if (meta?.expiries?.length) {
            setExpiries(meta.expiries);

            // Default selection: nearest expiry on first load (when nothing is selected yet)
            if (selectedExpiriesRef.current.length === 0 && meta.expiries.length > 0) {
              const nearest = meta.expiries[0].date;
              setSelectedExpiries([nearest]);
              selectedExpiriesRef.current = [nearest];
              // Fetch rows for the default selection
              fetchSnapshot([nearest]);
              return;
            }
          }

          if (meta?.underlying_price) {
            setUnderlyingPrice(meta.underlying_price);
          }
          if (meta?.health) {
            setHealth(meta.health);
          }

          // Refresh rows for the currently selected expiries
          if (selectedExpiriesRef.current.length > 0) {
            fetchSnapshot(selectedExpiriesRef.current);
          }
        });

        socket.on('oi_spike', (spike) => {
          console.log('[OI] Spike detected:', spike);
          setSpikes(prev => [spike, ...prev].slice(0, 200));
          // Show toast notification
          setToastSpike(spike);
          setToastOpen(true);
        });

        setConnectionStatus('connecting');
        socketRef.current = socket;
      } catch (err) {
        console.error('[OI] Failed to connect:', err);
        setConnectionStatus('disconnected');
      }
    };

    connectOI();
    fetchSpikes();

    return () => {
      if (socket) {
        socket.disconnect();
        socket = null;
      }
      if (fetchAbortRef.current) {
        fetchAbortRef.current.abort();
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ------------------------------------------------------------------
  // Expiry filter change → fetch new data
  // ------------------------------------------------------------------
  const handleExpiryFilterChange = useCallback((newSelectedExpiries) => {
    setSelectedExpiries(newSelectedExpiries);
    fetchSnapshot(newSelectedExpiries);
  }, [fetchSnapshot]);

  // ------------------------------------------------------------------
  // Unique strike count (using Set — not length/2 which breaks on asymmetric data)
  // ------------------------------------------------------------------
  const strikeCount = useMemo(
    () => new Set(filteredRows.map(r => r.strike)).size,
    [filteredRows]
  );

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  return (
    <div style={{ padding: '0 16px' }}>
      <CollapsibleCard
        title="Open Interest Aggregator"
        id="oi-dashboard"
        defaultExpanded={true}
      >
        {/* ── Connection Status Bar ─────────────────────────── */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 16px',
          borderRadius: '8px',
          background: isStale
            ? 'rgba(245, 158, 11, 0.08)'
            : 'rgba(30, 41, 59, 0.5)',
          border: `1px solid ${isStale ? 'rgba(245, 158, 11, 0.3)' : 'rgba(51, 65, 85, 0.5)'}`,
          marginBottom: '16px',
          flexWrap: 'wrap',
          gap: '8px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              width: '8px', height: '8px', borderRadius: '50%',
              backgroundColor: STATUS_COLORS[connectionStatus],
              boxShadow: connectionStatus === 'connected'
                ? `0 0 6px ${STATUS_COLORS.connected}` : 'none',
            }} />
            <span style={{ fontSize: '13px', color: '#94a3b8' }}>
              OI: <strong style={{ color: '#e2e8f0' }}>{connectionStatus}</strong>
            </span>
            {isStale && (
              <span style={{
                fontSize: '11px', color: '#f59e0b', fontWeight: 600,
                padding: '2px 6px', borderRadius: '4px',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
              }}>
                ⚠ STALE DATA
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {lastUpdated && (
              <span style={{ fontSize: '12px', color: '#64748b' }}>
                Updated: {lastUpdated}
              </span>
            )}
            <button
              onClick={() => fetchSnapshot(selectedExpiries)}
              style={{
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                color: '#60a5fa',
                border: '1px solid rgba(59, 130, 246, 0.3)',
                borderRadius: '6px',
                padding: '4px 10px',
                fontSize: '12px',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
              onMouseOver={e => e.target.style.backgroundColor = 'rgba(59, 130, 246, 0.2)'}
              onMouseOut={e => e.target.style.backgroundColor = 'rgba(59, 130, 246, 0.1)'}
            >
              ↻ Refresh
            </button>
          </div>
        </div>

        {/* ── Expiry Filter ─────────────────────────────────── */}
        <ExpiryFilter
          expiries={expiries}
          selectedExpiries={selectedExpiries}
          onChange={handleExpiryFilterChange}
          maxSelections={5}
        />

        {/* ── Summary Strip ─────────────────────────────────── */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
          gap: '12px',
          marginBottom: '16px',
        }}>
          {[
            { label: 'Call OI', value: summary.total_call_oi, color: '#f44336' },
            { label: 'Put OI', value: summary.total_put_oi, color: '#4caf50' },
            { label: 'PCR', value: summary.pcr, color: summary.pcr > 1 ? '#4caf50' : '#f44336', raw: true },
            { label: 'Strikes', value: strikeCount, color: '#60a5fa', raw: true },
            {
              label: underlyingPrice ? 'BTC Spot' : 'Expiries',
              value: underlyingPrice
                ? `$${Math.round(underlyingPrice).toLocaleString()}`
                : selectedExpiries.length > 0 ? selectedExpiries.length.toString() : '—',
              color: '#94a3b8',
              text: true,
            },
          ].map(item => (
            <div key={item.label} style={{
              padding: '12px 14px',
              borderRadius: '8px',
              background: 'rgba(15, 23, 42, 0.4)',
              border: '1px solid rgba(51, 65, 85, 0.4)',
            }}>
              <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '4px', textTransform: 'uppercase' }}>
                {item.label}
              </div>
              <div style={{
                fontSize: '16px', fontWeight: 700, color: item.color,
                fontFamily: item.text ? 'inherit' : 'monospace',
              }}>
                {item.text
                  ? item.value
                  : item.raw
                    ? Number(item.value || 0).toFixed(item.label === 'PCR' ? 4 : 0)
                    : formatNumber(item.value)
                }
              </div>
            </div>
          ))}
        </div>

        {/* ── Tab Bar ───────────────────────────────────────── */}
        <div style={{
          display: 'flex',
          gap: '4px',
          marginBottom: '16px',
          borderBottom: '1px solid rgba(51, 65, 85, 0.4)',
          paddingBottom: '0',
        }}>
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '8px 16px',
                fontSize: '13px',
                fontWeight: activeTab === tab.id ? 600 : 400,
                color: activeTab === tab.id ? '#e2e8f0' : '#64748b',
                backgroundColor: activeTab === tab.id ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                border: 'none',
                borderBottom: activeTab === tab.id ? '2px solid #3b82f6' : '2px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.15s',
                borderRadius: '6px 6px 0 0',
              }}
              onMouseOver={e => {
                if (activeTab !== tab.id) e.target.style.color = '#94a3b8';
              }}
              onMouseOut={e => {
                if (activeTab !== tab.id) e.target.style.color = '#64748b';
              }}
            >
              {tab.label}
              {tab.id === 'spikes' && spikes.length > 0 && (
                <span style={{
                  marginLeft: '6px', fontSize: '10px', padding: '1px 5px',
                  borderRadius: '8px', backgroundColor: 'rgba(239, 68, 68, 0.2)',
                  color: '#fca5a5',
                }}>
                  {spikes.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── No-expiry selected state ───────────────────────── */}
        {selectedExpiries.length === 0 && expiries.length > 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            minHeight: '200px', color: '#64748b', fontSize: '14px',
            flexDirection: 'column', gap: '8px',
          }}>
            <span>Select at least one expiry above</span>
          </div>
        )}

        {/* ── Tab Content ───────────────────────────────────── */}
        {selectedExpiries.length > 0 && (
          <div style={{ minHeight: '300px' }}>
            {activeTab === 'change' && (
              <OIChangeChart data={filteredRows} atmStrike={atmStrike} />
            )}
            {activeTab === 'absolute' && (
              <OIBarChart data={filteredRows} atmStrike={atmStrike} />
            )}
            {activeTab === 'table' && (
              <OITable data={filteredRows} atmStrike={atmStrike} />
            )}
            {activeTab === 'spikes' && (
              <OISpikeLog spikes={spikes} />
            )}
          </div>
        )}

        {/* ── Exchange Health Footer ────────────────────────── */}
        {health?.exchanges && Object.keys(health.exchanges).length > 0 && (
          <div style={{
            display: 'flex',
            gap: '12px',
            marginTop: '16px',
            padding: '8px 12px',
            borderRadius: '6px',
            background: 'rgba(15, 23, 42, 0.3)',
            border: '1px solid rgba(51, 65, 85, 0.3)',
            flexWrap: 'wrap',
          }}>
            {Object.entries(health.exchanges).map(([ex, info]) => {
              const age = info.last_fetch_ts
                ? Math.round((Date.now() - new Date(info.last_fetch_ts).getTime()) / 1000)
                : null;
              const statusIcon = age === null ? '⏳' : age < 90 ? '✅' : age < 180 ? '⚠️' : '❌';
              return (
                <span key={ex} style={{
                  fontSize: '11px', color: '#94a3b8',
                  display: 'flex', alignItems: 'center', gap: '4px',
                }}>
                  {statusIcon}
                  <span style={{ textTransform: 'capitalize' }}>{ex.replace('_', ' ')}</span>
                  {age !== null && (
                    <span style={{ color: '#64748b' }}>({age}s ago, {info.row_count} rows)</span>
                  )}
                </span>
              );
            })}
          </div>
        )}
      </CollapsibleCard>

      {/* ── Spike Toast Notification ──────────────────────── */}
      <Snackbar
        open={toastOpen}
        autoHideDuration={6000}
        onClose={() => setToastOpen(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={() => setToastOpen(false)}
          severity={toastSpike?.severity === 'high' ? 'error' : 'warning'}
          variant="filled"
          sx={{ minWidth: '280px', fontSize: '13px' }}
        >
          <strong>OI Spike {toastSpike?.severity === 'high' ? '🔴' : '🟡'}</strong>
          {toastSpike && (
            <div style={{ marginTop: '4px', fontSize: '12px' }}>
              {toastSpike.exchange} · {String(toastSpike.type).toUpperCase()} ·
              Strike {Number(toastSpike.strike).toLocaleString()} ·{' '}
              {toastSpike.change_pct > 0 ? '+' : ''}{toastSpike.change_pct?.toFixed(1)}%
            </div>
          )}
        </Alert>
      </Snackbar>
    </div>
  );
}
