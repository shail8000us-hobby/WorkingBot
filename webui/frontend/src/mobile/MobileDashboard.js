import React, { useState, useMemo } from 'react';
import { useMMM } from '../components/mmm/MMMContext';
import useMMMWebSocket from '../components/mmm/hooks/useMMMWebSocket';
import mmmService from '../components/mmm/mmmService';
import { Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material';
import '../mobile/mobile.css';

const MobileDashboard = ({ socket }) => {
    const { activeSessions, connectionStatus } = useMMM();
    const session = activeSessions[0];
    const sessionId = session?.session_id;

    const ws = useMMMWebSocket(sessionId, socket);
    const [pauseConfirmOpen, setPauseConfirmOpen] = useState(false);

    // Calculate time to expiry (0DTE trading)
    const timeToExpiry = useMemo(() => {
        if (!session?.expiry_timestamp) return null;

        const now = Date.now();
        const expiry = new Date(session.expiry_timestamp).getTime();
        const diff = expiry - now;

        if (diff <= 0) return 'EXPIRED';

        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

        if (hours > 0) return `${hours}h ${minutes}m`;
        return `${minutes}m`;
    }, [session?.expiry_timestamp, ws.heartbeat?.timestamp]); // Re-calculate on heartbeat updates

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

    const handlePause = async () => {
        if (session.status === 'RUNNING') {
            await mmmService.pauseSession(sessionId);
        } else if (session.status === 'PAUSED') {
            await mmmService.resumeSession(sessionId);
        }
        setPauseConfirmOpen(false);
    };

    const pnlColor = (session.net_pnl || 0) >= 0 ? '#4caf50' : '#f44336';
    const spotPrice = ws.heartbeat?.spot_price || session.spot_price || 'Loading...';

    // Calculate distance from spot for CE and PE
    const ceStrike = parseFloat(session.ce_strike) || 0;
    const peStrike = parseFloat(session.pe_strike) || 0;
    const spot = parseFloat(spotPrice) || 0;

    const ceDistance = ceStrike && spot ? ceStrike - spot : null;
    const peDistance = peStrike && spot ? spot - peStrike : null;

    // Distance color (green = far, red = close)
    const getDistanceColor = (distance) => {
        if (!distance) return '#777';
        const absDist = Math.abs(distance);
        if (absDist > 2000) return '#4caf50';
        if (absDist > 1000) return '#f39c12';
        return '#f44336';
    };

    // P&L Gauge (visual percentage bar)
    const maxLoss = parseFloat(session.params?.max_loss_usd) || 200;
    const pnlPercentage = Math.min(Math.abs((session.net_pnl || 0) / maxLoss) * 100, 100);

    return (
        <div className="mobile-screen">
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
            </div>

            {/* 3. BTC Spot */}
            <div className="mobile-card" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '13px', color: '#aaa', textTransform: 'uppercase', fontWeight: 600 }}>BTC Spot Price</div>
                <h1 style={{ margin: '8px 0 0 0', color: '#fff', fontSize: '32px' }}>${spotPrice}</h1>
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
                        ${(session.net_pnl || 0).toFixed(2)}
                    </h1>
                    <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: 12, fontSize: '12px', color: '#aaa' }}>
                        <span>Realized: <b style={{ color: '#fff' }}>${(session.realized_pnl || 0).toFixed(2)}</b></span>
                        <span>Unrealized: <b style={{ color: '#fff' }}>${(session.unrealized_pnl || 0).toFixed(2)}</b></span>
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
            <div className="mobile-card">
                <h4 style={{ margin: '0 0 12px 0', color: '#4caf50', textAlign: 'center', fontSize: '15px' }}>CE Side (Call)</h4>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: 8 }}>
                    <span style={{ color: '#aaa' }}>Strike: <b style={{ color: '#fff', fontSize: '15px' }}>{session.ce_strike || '—'}</b></span>
                    <span style={{ color: '#aaa' }}>Lots: <b style={{ color: '#fff', fontSize: '15px' }}>{session.ce_active_lots || 0}</b></span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                    <span style={{ color: '#aaa' }}>Fill: <b style={{ color: '#fff' }}>${session.ce_fill_price ? Number(session.ce_fill_price).toFixed(2) : '—'}</b></span>
                    {ceDistance !== null && (
                        <span style={{ color: getDistanceColor(ceDistance), fontWeight: 600 }}>
                            {ceDistance > 0 ? '+' : ''}{ceDistance.toFixed(0)} pts
                        </span>
                    )}
                </div>
            </div>

            <div className="mobile-card">
                <h4 style={{ margin: '0 0 12px 0', color: '#f44336', textAlign: 'center', fontSize: '15px' }}>PE Side (Put)</h4>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: 8 }}>
                    <span style={{ color: '#aaa' }}>Strike: <b style={{ color: '#fff', fontSize: '15px' }}>{session.pe_strike || '—'}</b></span>
                    <span style={{ color: '#aaa' }}>Lots: <b style={{ color: '#fff', fontSize: '15px' }}>{session.pe_active_lots || 0}</b></span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                    <span style={{ color: '#aaa' }}>Fill: <b style={{ color: '#fff' }}>${session.pe_fill_price ? Number(session.pe_fill_price).toFixed(2) : '—'}</b></span>
                    {peDistance !== null && (
                        <span style={{ color: getDistanceColor(peDistance), fontWeight: 600 }}>
                            {peDistance > 0 ? '+' : ''}{peDistance.toFixed(0)} pts
                        </span>
                    )}
                </div>
            </div>

            {/* 7. Risk Status */}
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

            {/* 8. PAUSE Button */}
            <div style={{ marginTop: 24, paddingBottom: 24 }}>
                <button
                    className={session.status === 'RUNNING' ? "mobile-btn mobile-btn-pause" : "mobile-btn"}
                    style={session.status !== 'RUNNING' ? { background: '#4caf50', color: '#fff' } : {}}
                    onClick={() => setPauseConfirmOpen(true)}
                    disabled={!isConnected}
                >
                    {session.status === 'RUNNING' ? 'PAUSE SESSION' : session.status === 'PAUSED' ? 'RESUME SESSION' : 'START SESSION'}
                </button>
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
                        <button className="mobile-btn" onClick={handlePause} style={{ background: '#4caf50', color: '#fff', width: '100%', minHeight: 64 }}>
                            CONFIRM
                        </button>
                    </DialogActions>
                </div>
            </Dialog>
        </div>
    );
};

export default React.memo(MobileDashboard);
