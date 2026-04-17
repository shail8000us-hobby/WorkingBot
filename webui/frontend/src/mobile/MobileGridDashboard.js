import React, { Suspense } from 'react';
import '../mobile/mobile.css';

// Lazy load the existing desktop panels
const MonitoringDashboard = React.lazy(() => import('../components/MonitoringDashboard'));
const MarketSignalPanel = React.lazy(() => import('../components/MarketSignalPanel'));

const MobileGridDashboard = ({ botIsRunning, botStatus, config, socket, latencyStats, connectionQuality, pnlSummary }) => {
    return (
        <div className="mobile-screen pb-24" style={{ overflowY: 'auto', WebkitOverflowScrolling: 'touch' }}>
            <div style={{ marginBottom: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h2 style={{ margin: 0, color: '#fff', fontSize: '24px' }}>Grid Dashboard</h2>
                    <span style={{ 
                        background: botIsRunning ? '#2ecc71' : '#e74c3c', 
                        padding: '4px 12px', 
                        borderRadius: '20px', 
                        fontSize: '12px', 
                        fontWeight: 'bold', 
                        color: '#fff' 
                    }}>
                        {botIsRunning ? 'LIVE' : 'IDLE'}
                    </span>
                </div>
                <p style={{ margin: '8px 0 0 0', color: '#aaa', fontSize: '14px' }}>
                    Real-time market activity and grid performance
                </p>
            </div>

            <Suspense fallback={<div className="mobile-card" style={{ padding: 20, textAlign: 'center', color: '#aaa' }}>Loading Grid Data...</div>}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {/* Monitoring & Limits */}
                    <div className="mobile-card">
                        <MonitoringDashboard botStatus={botStatus} config={config} isMobile={true} />
                    </div>

                    {/* Market Signals */}
                    <div className="mobile-card" style={{ overflowX: 'hidden' }}>
                        <MarketSignalPanel isMobile={true} />
                    </div>
                </div>
            </Suspense>
        </div>
    );
};

export default React.memo(MobileGridDashboard);
