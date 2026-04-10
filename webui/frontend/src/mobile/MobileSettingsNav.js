import React from 'react';
import { useNavigate } from 'react-router-dom';
import '../mobile/mobile.css';

const SettingsItem = ({ title, description, route, icon, onClick }) => {
    const navigate = useNavigate();

    const handleClick = () => {
        if (onClick) {
            onClick();
        } else if (route) {
            navigate(route);
        }
    };

    return (
        <div
            className="mobile-card"
            onClick={handleClick}
            style={{
                cursor: 'pointer',
                borderLeft: '4px solid #3498db',
                touchAction: 'manipulation',
                minHeight: '56px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
            }}
        >
            <div style={{ flex: 1 }}>
                <div style={{ fontSize: '16px', fontWeight: 600, color: '#fff', marginBottom: 4 }}>
                    {icon && <span style={{ marginRight: 8 }}>{icon}</span>}
                    {title}
                </div>
                {description && (
                    <div style={{ fontSize: '13px', color: '#aaa' }}>
                        {description}
                    </div>
                )}
            </div>
            <div style={{ fontSize: '20px', color: '#666', marginLeft: 12 }}>›</div>
        </div>
    );
};

const MobileSettingsNav = () => {
    return (
        <div className="mobile-screen">
            <div style={{ marginBottom: 24 }}>
                <h2 style={{ margin: 0, color: '#fff', fontSize: '24px' }}>Settings</h2>
                <p style={{ margin: '8px 0 0 0', color: '#aaa', fontSize: '14px' }}>
                    Configure bot parameters, risk controls, and system settings
                </p>
            </div>

            {/* MMM Settings */}
            <SettingsItem
                icon="💰"
                title="MMM Settings"
                description="Configure MMM algorithm parameters and risk limits"
                route="/mmm"
            />

            {/* Bot Configuration */}
            <SettingsItem
                icon="⚙️"
                title="Bot Configuration"
                description="Trading parameters, grid settings, and reconciliation"
                route="/config"
            />

            {/* Risk & Safety */}
            <SettingsItem
                icon="🛡️"
                title="Risk & Safety"
                description="Risk analytics, safety thresholds, and protection systems"
                route="/risk"
            />

            {/* Bot Management */}
            <SettingsItem
                icon="🤖"
                title="Bot Management"
                description="Process control, tmux sessions, emergency controls"
                route="/botmanagement"
            />

            {/* Options Settings */}
            <SettingsItem
                icon="📈"
                title="Options Trading"
                description="Options positions, auto-hedge, strategy settings"
                route="/options"
            />

            {/* Advanced Features */}
            <SettingsItem
                icon="🚀"
                title="Advanced Features"
                description="Data collection, technical indicators, research tools"
                route="/advanced_features"
            />

            {/* About Section */}
            <div className="mobile-card" style={{ marginTop: 24, background: '#1a1a2e', border: '1px solid #333' }}>
                <div style={{ fontSize: '12px', color: '#777', textAlign: 'center' }}>
                    <div>SSR Trading Bot v5.0</div>
                    <div style={{ marginTop: 4 }}>Mobile UI Optimized</div>
                </div>
            </div>
        </div>
    );
};

export default React.memo(MobileSettingsNav);
