import React from 'react';
import '../mobile/mobile.css';

/**
 * Wraps complex Desktop Algo dashboards in a CSS container
 * that forces them to stack vertically, shrink tables, and reflow
 * for iPhone 16 natively, WITHOUT editing their desktop source files!
 */
const MobileUniversalWrapper = ({ children, title }) => {
    return (
        <div className="mobile-screen pb-24 mobile-override-desktop" style={{ WebkitOverflowScrolling: 'touch', minHeight: '100vh', background: '#0a0a0f', paddingTop: '12px' }}>
            {title && (
                <div style={{ marginBottom: 12, padding: '0 12px' }}>
                    <h2 style={{ margin: 0, color: '#fff', fontSize: '24px' }}>{title}</h2>
                    <p style={{ margin: '4px 0 0 0', color: '#aaa', fontSize: '13px' }}>
                        Mobile optimized view
                    </p>
                </div>
            )}
            <div style={{ position: 'relative', width: '100%', overflowX: 'hidden' }}>
                {children}
            </div>
        </div>
    );
};

export default React.memo(MobileUniversalWrapper);
