import React, { Suspense } from 'react';
import '../mobile/mobile.css';

// Lazy load the exact desktop MMM structure component directly
const MMMDashboard = React.lazy(() => import('../components/mmm/MMMDashboard'));

const MobileMMMView = ({ socket, isMobile }) => {
    return (
        <div className="mobile-screen pb-24 mobile-override-desktop" style={{ WebkitOverflowScrolling: 'touch', minHeight: '100vh', background: '#0a0a0f', paddingTop: '12px' }}>
            <div style={{ position: 'relative', width: '100%', overflowX: 'hidden' }}>
                <Suspense fallback={<div style={{ color: '#aaa', textAlign: 'center', padding: '40px' }}>Loading full MMM Analytics...</div>}>
                    <MMMDashboard socket={socket} isMobile={isMobile} />
                </Suspense>
            </div>
        </div>
    );
};

export default React.memo(MobileMMMView);
