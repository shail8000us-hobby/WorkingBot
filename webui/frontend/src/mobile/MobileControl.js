import React, { useState } from 'react';
import { useMMM } from '../components/mmm/MMMContext';
import useMMMWebSocket from '../components/mmm/hooks/useMMMWebSocket';
import mmmService from '../components/mmm/mmmService';
import { Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material';
import '../mobile/mobile.css';

const MobileControl = ({ socket }) => {
    const { activeSessions, connectionStatus } = useMMM();
    const session = activeSessions[0];
    const sessionId = session?.session_id;

    const ws = useMMMWebSocket(sessionId, socket);

    const [modalMode, setModalMode] = useState(null); // 'pause', 'stop', 'emergency', 'closeall'
    const [step, setStep] = useState(1);

    const isConnected = ws.connected && connectionStatus === 'connected';

    // Calculate risk metrics
    const activeLots = (session?.ce_active_lots || 0) + (session?.pe_active_lots || 0);
    const unrealizedPnl = session?.unrealized_pnl || 0;
    const netPnl = session?.net_pnl || 0;
    const maxLoss = parseFloat(session?.params?.max_loss_usd) || 200;
    const pnlPercentage = Math.abs(netPnl / maxLoss) * 100;

    const triggerModal = (mode) => {
        setModalMode(mode);
        setStep(1);
    };

    const closeModal = () => {
        setModalMode(null);
        setStep(1);
    };

    const assertSuccess = (result, fallbackMessage) => {
        if (!result?.success) {
            throw new Error(result?.error || result?.message || fallbackMessage);
        }
    };

    const handleAction = async () => {
        try {
            if (modalMode === 'pause' || modalMode === 'resume') {
                if (!sessionId) {
                    throw new Error('No active session selected');
                }
                const result = session?.status === 'RUNNING'
                    ? await mmmService.pauseSession(sessionId)
                    : await mmmService.resumeSession(sessionId);
                assertSuccess(result, 'Failed to update session state');
                closeModal();
            } else if (modalMode === 'stop') {
                if (step === 1) {
                    setStep(2);
                } else {
                    if (!sessionId) {
                        throw new Error('No active session selected');
                    }
                    const result = await mmmService.stopSession(sessionId);
                    assertSuccess(result, 'Failed to stop session');
                    closeModal();
                }
            } else if (modalMode === 'closeall') {
                if (step === 1) {
                    setStep(2);
                } else {
                    if (!sessionId) {
                        throw new Error('No active session selected');
                    }
                    const result = await mmmService.emergencyCloseAllPositions(
                        'mobile_close_all_positions',
                        [sessionId],
                        false,
                    );
                    assertSuccess(result, 'Failed to close all positions');
                    closeModal();
                }
            } else if (modalMode === 'emergency') {
                if (step === 1) {
                    setStep(2);
                } else {
                    const result = await mmmService.emergencyKillAllBots('mobile_emergency_override');
                    assertSuccess(result, 'Failed to kill all bots');
                    closeModal();
                }
            }
        } catch (err) {
            alert(`Action failed: ${err.message}`);
        }
    };

    return (
        <div className="mobile-screen">
            <div style={{ textAlign: 'center', marginBottom: 24, marginTop: 16 }}>
                <h2 style={{ color: isConnected ? '#4caf50' : '#f44336', margin: 0, fontSize: '22px' }}>
                    {isConnected ? 'LIVE WS CONNECTED' : 'WS DISCONNECTED'}
                </h2>
                {session && (
                    <div style={{ color: '#aaa', marginTop: 8, fontSize: '14px' }}>
                        Current State: <b style={{ color: '#fff', fontSize: '16px' }}>{session.status}</b>
                    </div>
                )}
            </div>

            {/* Risk Summary Card (if session active) */}
            {session && activeLots > 0 && (
                <div className="mobile-card" style={{
                    background: pnlPercentage > 70 ? '#c0392b22' : pnlPercentage > 40 ? '#f39c1222' : '#4caf5022',
                    border: `1px solid ${pnlPercentage > 70 ? '#c0392b' : pnlPercentage > 40 ? '#f39c12' : '#4caf50'}`,
                    marginBottom: 24
                }}>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '12px', color: '#aaa', textTransform: 'uppercase', fontWeight: 600 }}>
                            Position Summary
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: 12, fontSize: '14px' }}>
                            <div>
                                <div style={{ color: '#aaa', fontSize: '11px' }}>Active Lots</div>
                                <div style={{ color: '#fff', fontSize: '20px', fontWeight: 700 }}>{activeLots}</div>
                            </div>
                            <div>
                                <div style={{ color: '#aaa', fontSize: '11px' }}>Unrealized P&L</div>
                                <div style={{ color: unrealizedPnl >= 0 ? '#4caf50' : '#f44336', fontSize: '20px', fontWeight: 700 }}>
                                    ${unrealizedPnl.toFixed(2)}
                                </div>
                            </div>
                            <div>
                                <div style={{ color: '#aaa', fontSize: '11px' }}>Max Loss Used</div>
                                <div style={{ color: pnlPercentage > 70 ? '#c0392b' : pnlPercentage > 40 ? '#f39c12' : '#4caf50', fontSize: '20px', fontWeight: 700 }}>
                                    {pnlPercentage.toFixed(0)}%
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {!session ? (
                <div className="mobile-card" style={{ textAlign: 'center' }}>
                    <p style={{ color: '#aaa', margin: 0 }}>No Active Session</p>
                    <p style={{ color: '#777', fontSize: '12px', marginTop: 8 }}>
                        Controls will be available when a session is active
                    </p>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {/* Pause/Resume */}
                    <button
                        className="mobile-btn"
                        style={{ background: session.status === 'RUNNING' ? '#f1c40f' : '#4caf50', color: session.status === 'RUNNING' ? '#000' : '#fff' }}
                        onClick={() => triggerModal(session.status === 'RUNNING' ? 'pause' : 'resume')}
                        disabled={!isConnected}
                    >
                        {session.status === 'RUNNING' ? 'PAUSE SESSION' : 'RESUME SESSION'}
                    </button>

                    {/* Close All Positions */}
                    {activeLots > 0 && (
                        <button
                            className="mobile-btn"
                            style={{ background: '#e67e22', color: '#fff' }}
                            onClick={() => triggerModal('closeall')}
                            disabled={!isConnected}
                        >
                            CLOSE ALL POSITIONS ({activeLots} LOTS)
                        </button>
                    )}

                    {/* Stop Session */}
                    <button
                        className="mobile-btn"
                        style={{ background: '#e67e22', color: '#fff' }}
                        onClick={() => triggerModal('stop')}
                        disabled={!isConnected}
                    >
                        STOP SESSION
                    </button>

                    {/* Emergency Kill All */}
                    <button
                        className="mobile-btn mobile-btn-danger"
                        style={{ background: '#c0392b', color: '#fff', marginTop: '24px' }}
                        onClick={() => triggerModal('emergency')}
                    >
                        EMERGENCY KILL ALL BOTS
                    </button>
                </div>
            )}

            {/* Confirmation Modal */}
            <Dialog
                open={modalMode !== null}
                onClose={closeModal}
                fullScreen
                PaperProps={{ style: { backgroundColor: modalMode === 'emergency' ? '#4a0b0b' : '#1e1e2e', color: '#fff' } }}
            >
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '24px' }}>
                    <DialogTitle style={{ textAlign: 'center', fontSize: '28px', color: modalMode === 'emergency' || modalMode === 'closeall' ? '#e74c3c' : '#fff' }}>
                        {modalMode === 'emergency' ? 'EMERGENCY OVERRIDE' : modalMode === 'closeall' ? 'CLOSE ALL POSITIONS' : 'CONFIRM ACTION'}
                    </DialogTitle>
                    <DialogContent style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
                        {modalMode === 'pause' && (
                            <>
                                <h2>Pause session?</h2>
                                <p style={{ color: '#aaa', marginTop: 8 }}>Session ID: {sessionId}</p>
                            </>
                        )}
                        {modalMode === 'resume' && (
                            <>
                                <h2>Resume session?</h2>
                                <p style={{ color: '#aaa', marginTop: 8 }}>Session ID: {sessionId}</p>
                            </>
                        )}
                        {modalMode === 'closeall' && (
                            <>
                                <h2 style={{ color: '#e67e22' }}>Close {activeLots} Active Lots?</h2>
                                <div style={{ marginTop: 24, fontSize: '16px' }}>
                                    <p style={{ color: '#aaa' }}>Current Unrealized P&L:</p>
                                    <p style={{ color: unrealizedPnl >= 0 ? '#4caf50' : '#f44336', fontSize: '28px', fontWeight: 700, margin: '8px 0' }}>
                                        ${unrealizedPnl.toFixed(2)}
                                    </p>
                                    <p style={{ color: '#f39c12', fontSize: '14px', marginTop: 16 }}>
                                        This will immediately close ALL CE and PE positions at market price.
                                    </p>
                                </div>
                                {step === 1 ? (
                                    <p style={{ color: '#aaa', marginTop: 24 }}>Step 1 of 2</p>
                                ) : (
                                    <p style={{ color: '#e74c3c', fontSize: '18px', fontWeight: 'bold', marginTop: 24 }}>
                                        FINAL CONFIRMATION: Close {activeLots} lots?
                                    </p>
                                )}
                            </>
                        )}
                        {modalMode === 'stop' && (
                            <>
                                <h2>STOP Session {sessionId}?</h2>
                                {activeLots > 0 && (
                                    <div style={{ marginTop: 16, padding: '12px', background: '#f39c1222', border: '1px solid #f39c12', borderRadius: '8px' }}>
                                        <p style={{ color: '#f39c12', margin: 0, fontSize: '14px' }}>
                                            ⚠️ {activeLots} active lots will remain open
                                        </p>
                                    </div>
                                )}
                                {step === 1 ? <p style={{ color: '#aaa', marginTop: 24 }}>Step 1 of 2</p> : <p style={{ color: '#f39c12', marginTop: 24 }}>FINAL CONFIRMATION: Tap again to stop.</p>}
                            </>
                        )}
                        {modalMode === 'emergency' && (
                            <>
                                <h2 style={{ color: '#c0392b' }}>KILL ALL PROCESSES?</h2>
                                <p style={{ fontSize: '16px' }}>This bypasses ALL graceful shutdowns and forcefully kills all running bots on the server instantly.</p>
                                {activeLots > 0 && (
                                    <div style={{ marginTop: 16, padding: '12px', background: '#c0392b44', border: '2px solid #e74c3c', borderRadius: '8px' }}>
                                        <p style={{ color: '#e74c3c', margin: 0, fontSize: '16px', fontWeight: 'bold' }}>
                                            ⚠️ {activeLots} ACTIVE LOTS WILL REMAIN OPEN
                                        </p>
                                        <p style={{ color: '#f39c12', margin: '8px 0 0 0', fontSize: '14px' }}>
                                            Unrealized P&L at risk: ${unrealizedPnl.toFixed(2)}
                                        </p>
                                    </div>
                                )}
                                {step === 1 ? <p style={{ color: '#aaa', marginTop: 24 }}>Step 1 of 2</p> : <p style={{ color: '#e74c3c', fontSize: '20px', fontWeight: 'bold', marginTop: 24 }}>FINAL WARNING: DESTRUCTIVE ACTION</p>}
                            </>
                        )}
                    </DialogContent>
                    <DialogActions style={{ flexDirection: 'column', padding: '0 0 24px 0', gap: '16px' }}>
                        <button
                            className="mobile-btn"
                            onClick={closeModal}
                            style={{ background: '#555', color: '#fff', minHeight: 80, fontSize: '20px', width: '100%' }}
                        >
                            CANCEL
                        </button>
                        <button
                            className="mobile-btn"
                            onClick={handleAction}
                            style={{
                                background: modalMode === 'emergency' ? '#c0392b' : (modalMode === 'closeall' && step === 2 ? '#e67e22' : (modalMode === 'stop' && step === 2 ? '#e67e22' : '#4caf50')),
                                color: '#fff',
                                minHeight: 64,
                                width: '100%'
                            }}
                        >
                            {modalMode === 'emergency' ? (step === 1 ? 'TAP TO CONFIRM (1/2)' : 'YES, KILL ALL (2/2)') :
                                modalMode === 'closeall' ? (step === 1 ? 'TAP TO CONFIRM (1/2)' : `YES, CLOSE ${activeLots} LOTS (2/2)`) :
                                    modalMode === 'stop' ? (step === 1 ? 'TAP TO CONFIRM (1/2)' : 'YES, STOP SESSION (2/2)') :
                                        'CONFIRM'}
                        </button>
                    </DialogActions>
                </div>
            </Dialog>
        </div>
    );
};

export default React.memo(MobileControl);
