import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMMM } from '../components/mmm/MMMContext';
import useMMMWebSocket from '../components/mmm/hooks/useMMMWebSocket';
import mmmService from '../components/mmm/mmmService';
import { Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material';
import '../mobile/mobile.css';

const MobileDashboard = ({ socket }) => {
    const navigate = useNavigate();
    const {
        activeSessions,
        connectionStatus,
        fetchSessions,
        selectedSessionId,
        selectSession,
    } = useMMM();

    const [fullSession, setFullSession] = useState(null);
    const [fullSessionLoading, setFullSessionLoading] = useState(false);
    const [pauseConfirmOpen, setPauseConfirmOpen] = useState(false);
    const [criticalConfirm, setCriticalConfirm] = useState({ open: false, mode: null, step: 1 });
    const [actionBusy, setActionBusy] = useState(false);
    const [actionError, setActionError] = useState('');
    const [spotFallback, setSpotFallback] = useState(null);
    const lastSpotFetchMs = useRef(0);

    const sessions = useMemo(() => activeSessions || [], [activeSessions]);
    const fleetSummary = useMemo(() => {
        if (!sessions.length) {
            return {
                totalSessions: 0,
                running: 0,
                paused: 0,
                stopped: 0,
                totalLots: 0,
                totalPnl: 0,
            };
        }

        let running = 0;
        let paused = 0;
        let stopped = 0;
        let totalLots = 0;
        let totalPnl = 0;

        sessions.forEach((s) => {
            const st = String(s.status || '').toUpperCase();
            if (st === 'RUNNING') running += 1;
            else if (st === 'PAUSED') paused += 1;
            else if (st === 'STOPPED') stopped += 1;

            totalLots += (Number(s.ce_active_lots) || 0) + (Number(s.pe_active_lots) || 0);
            totalPnl += Number(s.net_pnl) || 0;
        });

        return {
            totalSessions: sessions.length,
            running,
            paused,
            stopped,
            totalLots,
            totalPnl,
        };
    }, [sessions]);

    const allSessionIds = useMemo(
        () => sessions.map((s) => s.session_id).filter(Boolean),
        [sessions]
    );

    const resolvedSessionId = useMemo(() => {
        if (!sessions.length) return null;
        if (selectedSessionId && sessions.some((s) => s.session_id === selectedSessionId)) {
            return selectedSessionId;
        }
        return sessions[0].session_id;
    }, [sessions, selectedSessionId]);

    useEffect(() => {
        if (resolvedSessionId && resolvedSessionId !== selectedSessionId) {
            selectSession(resolvedSessionId);
        }
    }, [resolvedSessionId, selectedSessionId, selectSession]);

    const summarySession = useMemo(
        () => sessions.find((s) => s.session_id === resolvedSessionId) || null,
        [sessions, resolvedSessionId]
    );

    const sessionId = summarySession?.session_id;

    const ws = useMMMWebSocket(sessionId, socket);

    useEffect(() => {
        let cancelled = false;
        async function loadFullSession() {
            if (!sessionId) {
                setFullSession(null);
                setFullSessionLoading(false);
                return;
            }
            setFullSessionLoading(true);
            try {
                const res = await mmmService.getSession(sessionId, false);
                if (!cancelled) {
                    setFullSession(res?.success ? (res.session || null) : null);
                }
            } catch {
                if (!cancelled) setFullSession(null);
            } finally {
                if (!cancelled) setFullSessionLoading(false);
            }
        }

        loadFullSession();
        return () => {
            cancelled = true;
        };
    }, [sessionId]);

    const session = fullSession || summarySession;

    const asNumber = (value) => {
        const n = Number(value);
        return Number.isFinite(n) ? n : null;
    };

    const firstNumber = (...values) => {
        for (const v of values) {
            const n = asNumber(v);
            if (n !== null) return n;
        }
        return null;
    };

    const fmtMoney = useCallback((value, digits = 2) => {
        const n = asNumber(value);
        if (n === null) return '—';
        return n.toLocaleString(undefined, {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        });
    }, []);

    const fmtTs = (tsRaw) => {
        if (!tsRaw) return '—';
        const d = new Date(tsRaw);
        if (Number.isNaN(d.getTime())) return '—';
        return d.toLocaleTimeString();
    };

    const toMs = useCallback((tsRaw) => {
        if (!tsRaw) return 0;
        const t = new Date(tsRaw).getTime();
        return Number.isFinite(t) ? t : 0;
    }, []);

    // Calculate time to expiry (0DTE trading)
    const timeToExpiry = (() => {
        if (!session?.expiry_timestamp) return null;

        const now = Date.now();
        const expiry = new Date(session.expiry_timestamp).getTime();
        const diff = expiry - now;

        if (diff <= 0) return 'EXPIRED';

        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

        if (hours > 0) return `${hours}h ${minutes}m`;
        return `${minutes}m`;
    })();

    const activityFeed = useMemo(() => {
        const entries = [];

        ws.adjustments.slice(-5).forEach((item) => {
            entries.push({
                type: 'Adjustment',
                tone: '#4caf50',
                ts: item.timestamp || item.ts,
                text: `${(item.side || '').toUpperCase() || 'SIDE'} ${item.lots ?? '?'} lots @ ${fmtMoney(item.premium, 2)}`,
            });
        });

        ws.shifts.slice(-4).forEach((item) => {
            entries.push({
                type: 'Shift',
                tone: '#03a9f4',
                ts: item.timestamp || item.ts,
                text: `${(item.side || '').toUpperCase() || 'SIDE'} → ${item.new_strike ?? item.strike ?? '—'}`,
            });
        });

        ws.reversals.slice(-4).forEach((item) => {
            entries.push({
                type: 'Reversal',
                tone: '#ab47bc',
                ts: item.timestamp || item.ts,
                text: item.message || `${item.prev_aggressor || 'prev'} → ${item.new_aggressor || 'new'}`,
            });
        });

        ws.closeEvents.slice(-4).forEach((item) => {
            entries.push({
                type: 'Close@5',
                tone: '#f39c12',
                ts: item.timestamp || item.ts,
                text: item.message || `${(item.side || '').toUpperCase() || 'SIDE'} ${item.lots ?? '?'} lots closed`,
            });
        });

        ws.safetyEvents.slice(-4).forEach((item) => {
            entries.push({
                type: 'Safety',
                tone: '#f44336',
                ts: item.timestamp || item.ts,
                text: item.message || 'Safety event',
            });
        });

        return entries
            .sort((a, b) => toMs(b.ts) - toMs(a.ts))
            .slice(0, 8);
    }, [ws.adjustments, ws.shifts, ws.reversals, ws.closeEvents, ws.safetyEvents, fmtMoney, toMs]);

    useEffect(() => {
        if (!sessionId) return;
        const now = Date.now();
        const hasSpot = Number.isFinite(Number(session?.spot_price))
            || Number.isFinite(Number(ws.heartbeat?.spot_price))
            || Number.isFinite(Number(ws.heartbeat?.spot));

        if (hasSpot) return;
        if (now - lastSpotFetchMs.current < 15000) return;

        lastSpotFetchMs.current = now;
        let cancelled = false;
        (async () => {
            try {
                const res = await mmmService.getSpotPrice('BTC');
                if (!cancelled && res?.success && Number.isFinite(Number(res.spot_price))) {
                    setSpotFallback(Number(res.spot_price));
                }
            } catch {
                // best effort
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [sessionId, session?.spot_price, ws.heartbeat?.spot_price, ws.heartbeat?.spot, ws.heartbeat?.timestamp]);

    if (!session) {
        return (
            <div className="mobile-screen">
                <div className="mobile-card" style={{ textAlign: 'center', marginTop: 40 }}>
                    <h3>No Active Sessions</h3>
                    <p style={{ color: '#777', fontSize: '14px', marginTop: 8 }}>
                        MMM sessions will appear here when active
                    </p>
                </div>
            </div>
        );
    }

    const isConnected = ws.connected && connectionStatus === 'connected';
    const connectionColor = isConnected ? '#4caf50' : '#f44336';

    const statusColors = {
        RUNNING: '#4caf50',
        PAUSED: '#ff9800',
        STOPPED: '#757575',
        BOTH_SIDES_UP: '#f44336',
        ERROR: '#f44336',
        PARTIAL_ENTRY: '#ff5722',
    };
    const statusColor = statusColors[session.status] || '#9e9e9e';

    const heartbeatTs = ws.heartbeat?.timestamp || ws.heartbeat?._price_tick_ts;
    const heartbeatAgeSec = heartbeatTs
        ? Math.max(0, Math.floor((Date.now() - toMs(heartbeatTs)) / 1000))
        : null;
    const heartbeatHealth = heartbeatAgeSec === null
        ? 'No heartbeat yet'
        : heartbeatAgeSec <= 20
            ? 'Fresh'
            : heartbeatAgeSec <= 90
                ? 'Delayed'
                : 'Stale';
    const heartbeatColor = heartbeatAgeSec === null
        ? '#888'
        : heartbeatAgeSec <= 20
            ? '#4caf50'
            : heartbeatAgeSec <= 90
                ? '#f39c12'
                : '#f44336';

    const handlePause = async () => {
        if (!sessionId) return;
        setActionError('');
        setActionBusy(true);
        try {
            if (session.status === 'RUNNING') {
                await mmmService.pauseSession(sessionId);
            } else if (session.status === 'PAUSED') {
                await mmmService.resumeSession(sessionId);
            }
        } catch (e) {
            setActionError(e?.response?.data?.error || e.message || 'Failed to update session state');
        } finally {
            setActionBusy(false);
            setPauseConfirmOpen(false);
        }
    };

    const handleCriticalAction = async () => {
        if (!sessionId || !criticalConfirm.mode) return;
        setActionError('');
        setActionBusy(true);
        try {
            if (criticalConfirm.mode === 'closeall') {
                await mmmService.emergencyCloseAllPositions(
                    'mobile_dashboard_close_all_positions',
                    [sessionId],
                    false,
                );
            } else if (criticalConfirm.mode === 'stop') {
                await mmmService.stopSession(sessionId, 'mobile_dashboard_stop');
            } else if (criticalConfirm.mode === 'closeall_all') {
                if (!allSessionIds.length) throw new Error('No active sessions');
                await mmmService.emergencyCloseAllPositions(
                    'mobile_dashboard_close_all_sessions',
                    allSessionIds,
                    false,
                );
            }
            setCriticalConfirm({ open: false, mode: null, step: 1 });
        } catch (e) {
            setActionError(e?.response?.data?.error || e.message || 'Action failed');
        } finally {
            setActionBusy(false);
        }
    };

    const requestCriticalAction = (mode) => {
        setCriticalConfirm({ open: true, mode, step: 1 });
    };

    const proceedCriticalStep = () => {
        if (criticalConfirm.step === 1) {
            setCriticalConfirm((prev) => ({ ...prev, step: 2 }));
            return;
        }
        handleCriticalAction();
    };

    const handleForceHeartbeat = async () => {
        if (!sessionId) return;
        setActionError('');
        setActionBusy(true);
        try {
            await mmmService.forceHeartbeat(sessionId);
        } catch (e) {
            setActionError(e?.response?.data?.error || e.message || 'Failed to force heartbeat');
        } finally {
            setActionBusy(false);
        }
    };

    const handleRefresh = async () => {
        setActionError('');
        setActionBusy(true);
        try {
            await fetchSessions(false);
            if (sessionId) {
                const res = await mmmService.getSession(sessionId, false);
                if (res?.success) setFullSession(res.session || null);
            }
        } catch (e) {
            setActionError(e?.response?.data?.error || e.message || 'Failed to refresh session data');
        } finally {
            setActionBusy(false);
        }
    };

    const ce = session.ce || {};
    const pe = session.pe || {};

    const realizedPnl = firstNumber(session.realized_pnl, 0);
    const unrealizedPnl = firstNumber(session.unrealized_pnl, 0);
    const totalFees = firstNumber(session.total_fees, 0);
    const netPnl = firstNumber(session.net_pnl, realizedPnl + unrealizedPnl - totalFees);
    const pnlColor = netPnl >= 0 ? '#4caf50' : '#f44336';

    const spot = firstNumber(
        ws.heartbeat?.spot_price,
        ws.heartbeat?.spot,
        session.spot_price,
        session._spot,
        session._last_spot,
        spotFallback,
    );

    const ceStrike = firstNumber(session.ce_strike, ce.active_strike, ce.original_strike, 0);
    const peStrike = firstNumber(session.pe_strike, pe.active_strike, pe.original_strike, 0);
    const ceLots = firstNumber(session.ce_active_lots, ce.active_lots, 0);
    const peLots = firstNumber(session.pe_active_lots, pe.active_lots, 0);
    const ceFill = firstNumber(session.ce_fill_price, ce.entry_fill_price, ce.original_premium, null);
    const peFill = firstNumber(session.pe_fill_price, pe.entry_fill_price, pe.original_premium, null);

    const premiumMap = ws.heartbeat?.premium_map || session._premium_map || {};
    const premiumFromMap = (strike, side) => {
        const nStrike = asNumber(strike);
        if (!nStrike) return null;
        const key = `${Math.round(nStrike)}:${side}`;
        return asNumber(premiumMap[key]);
    };
    const ceLivePremium = firstNumber(ws.heartbeat?.ce_premium, premiumFromMap(ceStrike, 'call'), null);
    const peLivePremium = firstNumber(ws.heartbeat?.pe_premium, premiumFromMap(peStrike, 'put'), null);

    // Calculate distance from spot for CE and PE
    const ceDistance = ceStrike && spot ? ceStrike - spot : null;
    const peDistance = peStrike && spot ? spot - peStrike : null;
    const ceDistancePct = ceDistance && spot ? (ceDistance / spot) * 100 : null;
    const peDistancePct = peDistance && spot ? (peDistance / spot) * 100 : null;

    // Distance color (green = far, red = close)
    const getDistanceColor = (distancePct) => {
        if (distancePct === null) return '#777';
        const absDist = Math.abs(distancePct);
        if (absDist > 3.0) return '#4caf50';
        if (absDist > 1.5) return '#f39c12';
        return '#f44336';
    };

    // P&L Gauge (visual percentage bar)
    const maxLoss = firstNumber(session.params?.max_loss_usd, session.params?.max_loss_amount, 200);
    const pnlPercentage = Math.min(Math.abs(netPnl / maxLoss) * 100, 100);

    const awaitingUserAction = ws.heartbeat?.awaiting_user_action || session._awaiting_user_action;
    const awaitingUserActionDetails = ws.heartbeat?.awaiting_user_action_details || session._awaiting_user_action_details || {};

    return (
        <div className="mobile-screen">
            {fleetSummary.totalSessions > 0 && (
                <div className="mobile-card" style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 12, color: '#9aa', marginBottom: 8, textTransform: 'uppercase', fontWeight: 700 }}>
                        MMM Fleet Overview
                    </div>
                    <div className="mobile-kpi-grid" style={{ marginBottom: 8 }}>
                        <div className="mobile-kpi-item">
                            <div className="mobile-kpi-label">Sessions</div>
                            <div className="mobile-kpi-value">{fleetSummary.totalSessions}</div>
                        </div>
                        <div className="mobile-kpi-item">
                            <div className="mobile-kpi-label">Total Lots</div>
                            <div className="mobile-kpi-value">{fleetSummary.totalLots.toFixed(0)}</div>
                        </div>
                        <div className="mobile-kpi-item">
                            <div className="mobile-kpi-label">Running / Paused</div>
                            <div className="mobile-kpi-value">{fleetSummary.running} / {fleetSummary.paused}</div>
                        </div>
                        <div className="mobile-kpi-item">
                            <div className="mobile-kpi-label">Fleet P&L</div>
                            <div className="mobile-kpi-value" style={{ color: fleetSummary.totalPnl >= 0 ? '#4caf50' : '#f44336' }}>
                                ${fleetSummary.totalPnl.toFixed(2)}
                            </div>
                        </div>
                    </div>
                    {fleetSummary.totalSessions > 1 && (
                        <button
                            className="mobile-btn"
                            style={{ background: '#b71c1c', color: '#fff' }}
                            onClick={() => requestCriticalAction('closeall_all')}
                            disabled={actionBusy || !isConnected}
                        >
                            CLOSE ALL POSITIONS (ALL SESSIONS)
                        </button>
                    )}
                </div>
            )}

            {sessions.length > 1 && (
                <div className="mobile-card" style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 12, color: '#9aa', marginBottom: 8, textTransform: 'uppercase', fontWeight: 700 }}>
                        Active MMM Sessions ({sessions.length})
                    </div>
                    <div className="mobile-session-strip">
                        {sessions.map((s) => {
                            const selected = s.session_id === sessionId;
                            const sPnl = Number.isFinite(Number(s.net_pnl)) ? Number(s.net_pnl) : 0;
                            const sLots = (Number(s.ce_active_lots) || 0) + (Number(s.pe_active_lots) || 0);
                            return (
                                <button
                                    key={s.session_id}
                                    type="button"
                                    className={`mobile-session-chip ${selected ? 'mobile-session-chip-active' : ''}`}
                                    onClick={() => {
                                        selectSession(s.session_id);
                                        setFullSession(null);
                                        setActionError('');
                                    }}
                                >
                                    <div style={{ fontWeight: 700, fontSize: 12 }}>{s.session_id}</div>
                                    <div className="mobile-chip-meta">
                                        <span>{s.status || '—'}</span>
                                        <span>{sLots} lots</span>
                                        <span style={{ color: sPnl >= 0 ? '#4caf50' : '#f44336' }}>${sPnl.toFixed(2)}</span>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* 1. Connection Badge */}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, alignItems: 'center' }}>
                <span style={{ color: connectionColor, fontWeight: 600, fontSize: '14px' }}>
                    ● {isConnected ? 'LIVE WS' : 'DISCONNECTED'}
                </span>
                {timeToExpiry && (
                    <span style={{
                        color: timeToExpiry === 'EXPIRED' ? '#f44336' : '#f39c12',
                        fontWeight: 600,
                        fontSize: '14px',
                        background: timeToExpiry === 'EXPIRED' ? '#f4433622' : '#f39c1222',
                        padding: '4px 8px',
                        borderRadius: '6px',
                        border: `1px solid ${timeToExpiry === 'EXPIRED' ? '#f44336' : '#f39c12'}`
                    }}>
                        ⏱ {timeToExpiry}
                    </span>
                )}
            </div>

            <div className="mobile-card" style={{ marginBottom: 12, padding: '10px 12px' }}>
                <div className="mobile-row" style={{ marginBottom: 0 }}>
                    <span style={{ color: '#aaa', fontSize: 12 }}>Heartbeat</span>
                    <span style={{ color: heartbeatColor, fontSize: 12, fontWeight: 700 }}>
                        {heartbeatHealth}
                        {heartbeatAgeSec !== null ? ` • ${heartbeatAgeSec}s ago` : ''}
                    </span>
                </div>
            </div>

            {/* Connection Lost Overlay */}
            {!isConnected && (
                <div className="mobile-card" style={{ background: '#f4433622', border: '1px solid #f44336', marginBottom: 16 }}>
                    <div style={{ textAlign: 'center', color: '#f44336', fontWeight: 600 }}>
                        ⚠️ WebSocket Disconnected
                    </div>
                    <div style={{ textAlign: 'center', color: '#e74c3c', fontSize: '12px', marginTop: 4 }}>
                        Data may be stale. Reconnecting...
                    </div>
                </div>
            )}

            {/* 2. Session Status */}
            <div className="mobile-card" style={{ textAlign: 'center', background: `${statusColor}22`, border: `1px solid ${statusColor}` }}>
                <h2 style={{ color: statusColor, margin: 0, textTransform: 'uppercase', fontSize: '20px' }}>{session.status}</h2>
                <div style={{ fontSize: '11px', marginTop: 6, color: '#888' }}>Session: {sessionId}</div>
                {fullSessionLoading && (
                    <div style={{ fontSize: '11px', marginTop: 4, color: '#6b7280' }}>Syncing full session…</div>
                )}
            </div>

            {/* 3. BTC Spot */}
            <div className="mobile-card" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '13px', color: '#aaa', textTransform: 'uppercase', fontWeight: 600 }}>BTC Spot Price</div>
                <h1 style={{ margin: '8px 0 0 0', color: '#fff', fontSize: '32px' }}>
                    {spot !== null ? `$${fmtMoney(spot, 2)}` : '—'}
                </h1>
                {ws.heartbeat?.timestamp && (
                    <div style={{ fontSize: '11px', color: '#777', marginTop: 6 }}>
                        Updated: {new Date(ws.heartbeat.timestamp).toLocaleTimeString()}
                    </div>
                )}
            </div>

            {/* 4. PnL Card with Visual Gauge */}
            <div className="mobile-card" style={{ borderLeft: `4px solid ${pnlColor}` }}>
                <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '13px', color: '#aaa', textTransform: 'uppercase', fontWeight: 600 }}>Net P&L</div>
                    <h1 style={{ margin: '8px 0 0 0', color: pnlColor, fontSize: '32px' }}>
                        ${fmtMoney(netPnl, 2)}
                    </h1>
                    <div className="mobile-kpi-grid" style={{ marginTop: 12 }}>
                        <div className="mobile-kpi-item">
                            <div className="mobile-kpi-label">Realized</div>
                            <div className="mobile-kpi-value">${fmtMoney(realizedPnl, 2)}</div>
                        </div>
                        <div className="mobile-kpi-item">
                            <div className="mobile-kpi-label">Unrealized</div>
                            <div className="mobile-kpi-value">${fmtMoney(unrealizedPnl, 2)}</div>
                        </div>
                        <div className="mobile-kpi-item">
                            <div className="mobile-kpi-label">Fees</div>
                            <div className="mobile-kpi-value">${fmtMoney(totalFees, 2)}</div>
                        </div>
                        <div className="mobile-kpi-item">
                            <div className="mobile-kpi-label">Active Lots</div>
                            <div className="mobile-kpi-value">{(ceLots + peLots).toFixed(0)}</div>
                        </div>
                    </div>
                </div>

                {/* P&L Gauge Bar */}
                <div style={{ marginTop: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#777', marginBottom: 4 }}>
                        <span>Max Loss: ${maxLoss}</span>
                        <span>{pnlPercentage.toFixed(0)}% used</span>
                    </div>
                    <div style={{
                        height: '8px',
                        background: '#1a1a2e',
                        borderRadius: '4px',
                        overflow: 'hidden',
                        border: '1px solid #333'
                    }}>
                        <div style={{
                            height: '100%',
                            width: `${pnlPercentage}%`,
                            background: pnlColor,
                            transition: 'width 0.5s ease',
                            borderRadius: '3px'
                        }} />
                    </div>
                </div>
            </div>

            {/* 5 & 6. CE/PE side cards with distance indicators */}
            <div className="mobile-side-grid">
                <div className="mobile-card">
                    <h4 style={{ margin: '0 0 12px 0', color: '#4caf50', textAlign: 'center', fontSize: '15px' }}>CE Side (Call)</h4>
                    <div className="mobile-row">
                        <span style={{ color: '#aaa' }}>Strike</span>
                        <b style={{ color: '#fff' }}>{ceStrike || '—'}</b>
                    </div>
                    <div className="mobile-row">
                        <span style={{ color: '#aaa' }}>Lots</span>
                        <b style={{ color: '#fff' }}>{ceLots.toFixed(0)}</b>
                    </div>
                    <div className="mobile-row">
                        <span style={{ color: '#aaa' }}>Entry</span>
                        <b style={{ color: '#fff' }}>{ceFill !== null ? `$${fmtMoney(ceFill, 2)}` : '—'}</b>
                    </div>
                    <div className="mobile-row">
                        <span style={{ color: '#aaa' }}>Live Premium</span>
                        <b style={{ color: '#4caf50' }}>{ceLivePremium !== null ? `$${fmtMoney(ceLivePremium, 2)}` : '—'}</b>
                    </div>
                    <div className="mobile-row" style={{ marginBottom: 0 }}>
                        <span style={{ color: '#aaa' }}>Distance</span>
                        {ceDistance !== null ? (
                            <span style={{ color: getDistanceColor(ceDistancePct), fontWeight: 700 }}>
                                {ceDistance > 0 ? '+' : ''}{ceDistance.toFixed(0)} pts ({ceDistancePct.toFixed(2)}%)
                            </span>
                        ) : (
                            <span style={{ color: '#777' }}>—</span>
                        )}
                    </div>
                </div>

                <div className="mobile-card">
                    <h4 style={{ margin: '0 0 12px 0', color: '#f44336', textAlign: 'center', fontSize: '15px' }}>PE Side (Put)</h4>
                    <div className="mobile-row">
                        <span style={{ color: '#aaa' }}>Strike</span>
                        <b style={{ color: '#fff' }}>{peStrike || '—'}</b>
                    </div>
                    <div className="mobile-row">
                        <span style={{ color: '#aaa' }}>Lots</span>
                        <b style={{ color: '#fff' }}>{peLots.toFixed(0)}</b>
                    </div>
                    <div className="mobile-row">
                        <span style={{ color: '#aaa' }}>Entry</span>
                        <b style={{ color: '#fff' }}>{peFill !== null ? `$${fmtMoney(peFill, 2)}` : '—'}</b>
                    </div>
                    <div className="mobile-row">
                        <span style={{ color: '#aaa' }}>Live Premium</span>
                        <b style={{ color: '#f44336' }}>{peLivePremium !== null ? `$${fmtMoney(peLivePremium, 2)}` : '—'}</b>
                    </div>
                    <div className="mobile-row" style={{ marginBottom: 0 }}>
                        <span style={{ color: '#aaa' }}>Distance</span>
                        {peDistance !== null ? (
                            <span style={{ color: getDistanceColor(peDistancePct), fontWeight: 700 }}>
                                {peDistance > 0 ? '+' : ''}{peDistance.toFixed(0)} pts ({peDistancePct.toFixed(2)}%)
                            </span>
                        ) : (
                            <span style={{ color: '#777' }}>—</span>
                        )}
                    </div>
                </div>
            </div>

            {/* 7. Risk Status */}
            {awaitingUserAction && (
                <div className="mobile-card" style={{ background: '#8b000022', border: '1px solid #ff5252' }}>
                    <h4 style={{ margin: '0 0 6px 0', fontSize: '16px', color: '#ff6b6b' }}>🚨 Operator Action Required</h4>
                    <div style={{ fontSize: '13px', color: '#ffd7d7' }}>
                        {awaitingUserActionDetails.closed_side && awaitingUserActionDetails.open_side
                            ? `${String(awaitingUserActionDetails.closed_side).toUpperCase()} closed while ${String(awaitingUserActionDetails.open_side).toUpperCase()} is open.`
                            : 'Session is waiting for manual operator intervention.'}
                    </div>
                </div>
            )}

            {ws.bothSidesAlert && (
                <div className="mobile-card" style={{ background: '#c0392b', color: '#fff', border: '2px solid #e74c3c' }}>
                    <h4 style={{ margin: '0 0 8px 0', fontSize: '18px' }}>⚠️ Both Sides Up Alert</h4>
                    <div style={{ fontSize: '15px' }}>Active margin risk detected! Close positions immediately.</div>
                </div>
            )}
            {ws.safetyEvents && ws.safetyEvents.length > 0 && (
                <div className="mobile-card" style={{ background: '#e67e22', color: '#fff', border: '2px solid #f39c12' }}>
                    <h4 style={{ margin: '0 0 8px 0', fontSize: '16px' }}>🛡️ Safety Warning</h4>
                    <div style={{ fontSize: '14px' }}>{ws.safetyEvents[ws.safetyEvents.length - 1]?.message}</div>
                </div>
            )}

            {/* 8. Quick Actions */}
            {actionError && (
                <div className="mobile-card" style={{ background: '#f4433622', border: '1px solid #f44336' }}>
                    <div style={{ color: '#ff8a80', fontSize: '13px' }}>{actionError}</div>
                </div>
            )}

            <div className="mobile-card">
                <h4 style={{ margin: '0 0 12px 0', fontSize: '15px', color: '#90caf9' }}>Quick Actions</h4>
                <div className="mobile-actions-grid">
                    <button
                        className={session.status === 'RUNNING' ? 'mobile-btn mobile-btn-pause' : 'mobile-btn mobile-btn-success'}
                        onClick={() => setPauseConfirmOpen(true)}
                        disabled={!isConnected || actionBusy}
                    >
                        {session.status === 'RUNNING' ? 'PAUSE' : session.status === 'PAUSED' ? 'RESUME' : 'SESSION IDLE'}
                    </button>
                    <button
                        className="mobile-btn"
                        style={{ background: '#1976d2', color: '#fff' }}
                        onClick={handleForceHeartbeat}
                        disabled={!isConnected || actionBusy || !sessionId}
                    >
                        FORCE BEAT
                    </button>
                    <button
                        className="mobile-btn"
                        style={{ background: '#455a64', color: '#fff' }}
                        onClick={handleRefresh}
                        disabled={actionBusy}
                    >
                        REFRESH
                    </button>
                    <button
                        className="mobile-btn"
                        style={{ background: '#6a1b9a', color: '#fff' }}
                        onClick={() => navigate('/control')}
                        disabled={actionBusy}
                    >
                        OPEN CONTROL
                    </button>
                    <button
                        className="mobile-btn"
                        style={{ background: '#00897b', color: '#fff' }}
                        onClick={() => navigate('/risk')}
                        disabled={actionBusy}
                    >
                        OPEN RISK
                    </button>
                    <button
                        className="mobile-btn"
                        style={{ background: '#3949ab', color: '#fff' }}
                        onClick={() => navigate('/monitoring')}
                        disabled={actionBusy}
                    >
                        OPEN MONITOR
                    </button>
                    <button
                        className="mobile-btn"
                        style={{ background: '#e67e22', color: '#fff' }}
                        onClick={() => requestCriticalAction('stop')}
                        disabled={actionBusy || !isConnected}
                    >
                        STOP
                    </button>
                    <button
                        className="mobile-btn"
                        style={{ background: '#c0392b', color: '#fff' }}
                        onClick={() => requestCriticalAction('closeall')}
                        disabled={actionBusy || !isConnected}
                    >
                        CLOSE ALL
                    </button>
                </div>
            </div>

            {/* 9. Recent Activity */}
            <div className="mobile-card" style={{ marginTop: 12 }}>
                <h4 style={{ margin: '0 0 12px 0', fontSize: '15px', color: '#f5f5f5' }}>Recent Activity</h4>
                {activityFeed.length === 0 ? (
                    <div style={{ color: '#888', fontSize: '13px' }}>No events yet for this session.</div>
                ) : (
                    <div>
                        {activityFeed.map((event, idx) => (
                            <div key={`${event.type}-${idx}-${event.ts || idx}`} className="mobile-activity-item">
                                <div className="mobile-row" style={{ marginBottom: 4 }}>
                                    <span className="mobile-pill" style={{ borderColor: `${event.tone}77`, color: event.tone }}>
                                        {event.type}
                                    </span>
                                    <span style={{ color: '#777', fontSize: 11 }}>{fmtTs(event.ts)}</span>
                                </div>
                                <div style={{ color: '#ddd', fontSize: 13 }}>{event.text}</div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Confirmation Modal */}
            <Dialog
                open={pauseConfirmOpen}
                onClose={() => setPauseConfirmOpen(false)}
                fullScreen
                PaperProps={{ style: { backgroundColor: '#1e1e2e', color: '#fff' } }}
            >
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '24px' }}>
                    <DialogTitle style={{ textAlign: 'center', fontSize: '24px' }}>Confirm Action</DialogTitle>
                    <DialogContent style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <h3 style={{ textAlign: 'center' }}>
                            {session.status === 'RUNNING' ? 'Are you sure you want to PAUSE the session?' : 'Are you sure you want to RESUME?'}
                        </h3>
                    </DialogContent>
                    <DialogActions style={{ flexDirection: 'column', padding: '0 0 24px 0', gap: '16px' }}>
                        <button className="mobile-btn" onClick={() => setPauseConfirmOpen(false)} style={{ background: '#555', color: '#fff', minHeight: 64 }}>
                            CANCEL
                        </button>
                        <button className="mobile-btn" onClick={handlePause} style={{ background: '#4caf50', color: '#fff', width: '100%', minHeight: 64 }} disabled={actionBusy}>
                            {actionBusy ? 'PROCESSING...' : 'CONFIRM'}
                        </button>
                    </DialogActions>
                </div>
            </Dialog>

            <Dialog
                open={criticalConfirm.open}
                onClose={() => setCriticalConfirm({ open: false, mode: null, step: 1 })}
                fullScreen
                PaperProps={{ style: { backgroundColor: '#1e1e2e', color: '#fff' } }}
            >
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '24px' }}>
                    <DialogTitle style={{ textAlign: 'center', fontSize: '24px', color: criticalConfirm.mode === 'closeall' ? '#ff8a80' : '#f39c12' }}>
                        {criticalConfirm.mode === 'closeall'
                            ? 'Close ALL Positions'
                            : criticalConfirm.mode === 'closeall_all'
                                ? 'Close ALL Sessions'
                                : 'Stop Session'}
                    </DialogTitle>
                    <DialogContent style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', textAlign: 'center' }}>
                        {criticalConfirm.mode === 'closeall' ? (
                            <>
                                <h3>Session {sessionId}</h3>
                                <p style={{ color: '#aaa' }}>This closes CE and PE lots at market for this session.</p>
                            </>
                        ) : criticalConfirm.mode === 'closeall_all' ? (
                            <>
                                <h3>All Active MMM Sessions</h3>
                                <p style={{ color: '#aaa' }}>
                                    This sends emergency close for all {fleetSummary.totalSessions} active sessions.
                                </p>
                                <p style={{ color: '#ffb74d', fontWeight: 700, marginTop: 8 }}>
                                    Total lots affected: {fleetSummary.totalLots.toFixed(0)}
                                </p>
                            </>
                        ) : (
                            <>
                                <h3>Stop session {sessionId}?</h3>
                                <p style={{ color: '#aaa' }}>If lots are still open, risk remains in market.</p>
                            </>
                        )}
                        <p style={{ marginTop: 16, color: criticalConfirm.step === 1 ? '#aaa' : '#ffb74d', fontWeight: 700 }}>
                            {criticalConfirm.step === 1 ? 'Step 1 of 2' : 'Final confirmation'}
                        </p>
                    </DialogContent>
                    <DialogActions style={{ flexDirection: 'column', padding: '0 0 24px 0', gap: '16px' }}>
                        <button
                            className="mobile-btn"
                            onClick={() => setCriticalConfirm({ open: false, mode: null, step: 1 })}
                            style={{ background: '#555', color: '#fff', minHeight: 64 }}
                        >
                            CANCEL
                        </button>
                        <button
                            className="mobile-btn"
                            onClick={proceedCriticalStep}
                            style={{
                                background: criticalConfirm.mode === 'closeall' || criticalConfirm.mode === 'closeall_all' ? '#c0392b' : '#e67e22',
                                color: '#fff',
                                width: '100%',
                                minHeight: 64,
                            }}
                            disabled={actionBusy}
                        >
                            {actionBusy
                                ? 'PROCESSING...'
                                : criticalConfirm.step === 1
                                    ? 'TAP TO CONFIRM (1/2)'
                                    : (criticalConfirm.mode === 'closeall'
                                        ? 'YES, CLOSE ALL (2/2)'
                                        : criticalConfirm.mode === 'closeall_all'
                                            ? 'YES, CLOSE ALL SESSIONS (2/2)'
                                            : 'YES, STOP SESSION (2/2)')}
                        </button>
                    </DialogActions>
                </div>
            </Dialog>
        </div>
    );
};

export default React.memo(MobileDashboard);
