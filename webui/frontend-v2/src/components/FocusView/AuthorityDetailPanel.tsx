/**
 * AuthorityDetailPanel - Expanded view of authority layers
 * 
 * Shows the three decision-makers with inline styles (no CSS module needed).
 * Uses the actual type definitions from types/index.ts.
 */

import React from 'react';
import type { AuthorityState, ControllingAuthority } from '../../types';

interface AuthorityDetailPanelProps {
  authority: AuthorityState;
  controlledBy: ControllingAuthority;
}

// ============================================================================
// HEARTBEAT SECTION
// ============================================================================

const HeartbeatSection: React.FC<{
  heartbeat: AuthorityState['heartbeat'];
  isController: boolean;
}> = ({ heartbeat, isController }) => {
  const statusEmoji = 
    heartbeat.status === 'alive' ? '💚' :
    heartbeat.status === 'stale' ? '💛' : '❌';
  
  const statusLabel =
    heartbeat.status === 'alive' ? 'System Operational' :
    heartbeat.status === 'stale' ? 'Stale Data' : 'System Down';
  
  const formatLastSeen = () => {
    if (!heartbeat.lastSeen) return 'Never';
    const ago = Date.now() - heartbeat.lastSeen;
    if (ago < 1000) return 'Just now';
    if (ago < 60000) return `${Math.floor(ago / 1000)}s ago`;
    return `${Math.floor(ago / 60000)}m ago`;
  };
  
  return (
    <div style={{
      background: isController ? 'rgba(59, 130, 246, 0.1)' : 'rgba(30, 30, 40, 0.5)',
      border: `1px solid ${isController ? '#3b82f6' : '#333'}`,
      borderRadius: '8px',
      padding: '12px',
      marginBottom: '12px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        <span style={{ fontSize: '18px' }}>💓</span>
        <span style={{ fontWeight: 600, color: '#fff' }}>Heartbeat</span>
        <span style={{ fontSize: '11px', color: '#888' }}>Technical Permission</span>
        {isController && (
          <span style={{
            marginLeft: 'auto',
            background: '#ef4444',
            color: 'white',
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: 700
          }}>BLOCKING</span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: '#ccc' }}>
        <span>{statusEmoji}</span>
        <span>{statusLabel}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px', color: '#aaa' }}>
        <div>
          <div style={{ color: '#666', fontSize: '11px' }}>Last Heartbeat</div>
          <div>{formatLastSeen()}</div>
        </div>
        {heartbeat.reason && (
          <div>
            <div style={{ color: '#666', fontSize: '11px' }}>Reason</div>
            <div style={{ color: '#ef4444' }}>{heartbeat.reason}</div>
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================================================
// GUARDIAN SECTION
// ============================================================================

const GuardianSection: React.FC<{
  guardian: AuthorityState['guardian'];
  isController: boolean;
}> = ({ guardian, isController }) => {
  const statusEmoji = 
    guardian.status === 'permitting' ? '🟢' :
    guardian.status === 'warning' ? '🟡' : '🛑';
  
  const statusLabel =
    guardian.status === 'permitting' ? 'Trading Allowed' :
    guardian.status === 'warning' ? 'Approaching Limits' : 'Trading Blocked';
  
  return (
    <div style={{
      background: isController ? 'rgba(239, 68, 68, 0.1)' : 'rgba(30, 30, 40, 0.5)',
      border: `1px solid ${isController ? '#ef4444' : '#333'}`,
      borderRadius: '8px',
      padding: '12px',
      marginBottom: '12px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        <span style={{ fontSize: '18px' }}>🛡️</span>
        <span style={{ fontWeight: 600, color: '#fff' }}>Guardian</span>
        <span style={{ fontSize: '11px', color: '#888' }}>Capital Permission</span>
        {isController && (
          <span style={{
            marginLeft: 'auto',
            background: '#ef4444',
            color: 'white',
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: 700
          }}>BLOCKING</span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: '#ccc' }}>
        <span>{statusEmoji}</span>
        <span>{statusLabel}</span>
      </div>
      {guardian.blockedBy && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '6px',
          padding: '8px 12px',
          fontSize: '12px',
          color: '#ef4444'
        }}>
          {guardian.blockedBy}
        </div>
      )}
      <div style={{ marginTop: '8px', fontSize: '12px', color: '#aaa' }}>
        <span style={{ color: '#666' }}>Risk Level: </span>
        <span style={{
          color: guardian.riskLevel === 'critical' ? '#ef4444' :
                 guardian.riskLevel === 'high' ? '#eab308' : '#22c55e'
        }}>
          {guardian.riskLevel.toUpperCase()}
        </span>
      </div>
    </div>
  );
};

// ============================================================================
// TRADING SECTION
// ============================================================================

const TradingSection: React.FC<{
  trading: AuthorityState['trading'];
  isController: boolean;
}> = ({ trading, isController }) => {
  const intentEmoji = 
    trading.intent === 'active' ? '📈' :
    trading.intent === 'paused' ? '⏸️' : '💤';
  
  const intentLabel =
    trading.intent === 'active' ? 'Actively Trading' :
    trading.intent === 'paused' ? 'Paused' : 'Idle (No Signals)';
  
  const pausedByLabel = trading.pausedBy === 'user' ? 'User Command' : 
                        trading.pausedBy === 'system' ? 'System Override' : null;
  
  return (
    <div style={{
      background: isController ? 'rgba(34, 197, 94, 0.1)' : 'rgba(30, 30, 40, 0.5)',
      border: `1px solid ${isController ? '#22c55e' : '#333'}`,
      borderRadius: '8px',
      padding: '12px',
      marginBottom: '12px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        <span style={{ fontSize: '18px' }}>📈</span>
        <span style={{ fontWeight: 600, color: '#fff' }}>Trading Intent</span>
        <span style={{ fontSize: '11px', color: '#888' }}>Strategic Permission</span>
        {isController && (
          <span style={{
            marginLeft: 'auto',
            background: '#22c55e',
            color: 'white',
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: 700
          }}>IN CONTROL</span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: '#ccc' }}>
        <span>{intentEmoji}</span>
        <span>{intentLabel}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px', color: '#aaa' }}>
        {pausedByLabel && (
          <div>
            <div style={{ color: '#666', fontSize: '11px' }}>Paused By</div>
            <div>{pausedByLabel}</div>
          </div>
        )}
        {trading.pausedReason && (
          <div>
            <div style={{ color: '#666', fontSize: '11px' }}>Reason</div>
            <div>{trading.pausedReason}</div>
          </div>
        )}
        {trading.lastAction && (
          <div>
            <div style={{ color: '#666', fontSize: '11px' }}>Last Action</div>
            <div>{trading.lastAction}</div>
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const AuthorityDetailPanel: React.FC<AuthorityDetailPanelProps> = ({
  authority,
  controlledBy,
}) => {
  return (
    <div style={{
      background: '#1a1a24',
      border: '1px solid #333',
      borderRadius: '8px',
      padding: '16px'
    }}>
      <h4 style={{ margin: '0 0 4px', fontSize: '14px', fontWeight: 600, color: '#fff' }}>Authority Layers</h4>
      <p style={{ margin: '0 0 16px', fontSize: '12px', color: '#888' }}>
        Three independent decision-makers control trading. 
        The one highlighted is currently in control.
      </p>
      
      <HeartbeatSection 
        heartbeat={authority.heartbeat} 
        isController={controlledBy === 'heartbeat'}
      />
      <GuardianSection 
        guardian={authority.guardian} 
        isController={controlledBy === 'guardian'}
      />
      <TradingSection 
        trading={authority.trading} 
        isController={controlledBy === 'trading' || controlledBy === 'user'}
      />
    </div>
  );
};

export default AuthorityDetailPanel;
