import React from 'react';
import { useSocketConnection } from '../../hooks/useSocketConnection';

/**
 * ConnectionStatusBar — Always visible on mobile, shows WebSocket & network status
 * Placed at bottom of screen or in header on mobile views
 */
const ConnectionStatusBar = ({ connectionState = 'unknown', connectionQuality = 'unknown' }) => {
  const isConnected = connectionState === 'connected';
  const statusColor = isConnected ? '#4caf50' : '#f44336';
  const statusText = isConnected ? 'LIVE' : connectionState === 'reconnecting' ? 'RECONNECTING...' : 'OFFLINE';

  // Map quality to description
  const qualityMap = {
    'unknown': '?',
    'excellent': 'Excellent',
    'good': 'Good',
    'fair': 'Fair',
    'poor': 'Poor',
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 'calc(env(safe-area-inset-top) + 56px)', // Below TopBar
        left: 0,
        right: 0,
        background: isConnected ? '#1a1a2e' : '#4a0b0b',
        borderBottom: `2px solid ${statusColor}`,
        padding: '6px 12px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: '11px',
        color: '#aaa',
        zIndex: 40, // Below sidebar, above main content
        backdropFilter: 'blur(4px)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span
          style={{
            display: 'inline-block',
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: statusColor,
            animation: !isConnected ? 'pulse 1s infinite' : 'none',
          }}
        />
        <span style={{ color: statusColor, fontWeight: 600 }}>{statusText}</span>
      </div>
      <div style={{ color: '#666', fontSize: '10px' }}>
        {qualityMap[connectionQuality]}
      </div>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
};

export default React.memo(ConnectionStatusBar);
