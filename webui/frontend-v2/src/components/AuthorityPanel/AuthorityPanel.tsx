/**
 * Authority Panel - Compact view of three trading authorities
 * 
 * Uses inline styles for faster development (no CSS module build issues).
 * Shows: Heartbeat, Guardian, Trading - who is in control and why.
 */

import React from 'react';
import type { AuthorityState, ControllingAuthority } from '../../types';

interface AuthorityPanelProps {
  authority: AuthorityState;
  controlledBy: ControllingAuthority;
}

// Colors
const colors = {
  success: '#22c55e',
  warning: '#eab308',
  danger: '#ef4444',
  muted: '#666',
  text: '#fff',
  bg: 'rgba(30, 30, 40, 0.5)',
  border: '#333',
};

// Row styles
const rowStyle = (isController: boolean, statusColor: string): React.CSSProperties => ({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  padding: '8px 10px',
  background: isController ? `${statusColor}15` : 'transparent',
  borderLeft: isController ? `3px solid ${statusColor}` : '3px solid transparent',
  borderRadius: '4px',
  marginBottom: '4px',
});

// ============================================================================
// HEARTBEAT ROW
// ============================================================================

const HeartbeatRow: React.FC<{ 
  heartbeat: AuthorityState['heartbeat'];
  isController: boolean;
}> = ({ heartbeat, isController }) => {
  const config = {
    alive: { icon: '💓', label: 'ALIVE', color: colors.success },
    stale: { icon: '💔', label: 'STALE', color: colors.warning },
    dead: { icon: '💀', label: 'DEAD', color: colors.danger },
  }[heartbeat.status];
  
  return (
    <div style={rowStyle(isController, config.color)}>
      <span style={{ fontSize: '16px' }}>{config.icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: 500, color: colors.text, fontSize: '12px' }}>Heartbeat</span>
          <span style={{ 
            fontSize: '10px', 
            fontWeight: 600, 
            color: config.color,
            background: `${config.color}20`,
            padding: '1px 6px',
            borderRadius: '3px'
          }}>{config.label}</span>
        </div>
        {heartbeat.reason && (
          <div style={{ fontSize: '11px', color: colors.muted, marginTop: '2px' }}>
            {heartbeat.reason}
          </div>
        )}
      </div>
      {isController && (
        <span style={{ 
          fontSize: '9px', 
          fontWeight: 700, 
          color: colors.danger,
          background: `${colors.danger}20`,
          padding: '2px 6px',
          borderRadius: '3px'
        }}>BLOCKING</span>
      )}
    </div>
  );
};

// ============================================================================
// GUARDIAN ROW
// ============================================================================

const GuardianRow: React.FC<{ 
  guardian: AuthorityState['guardian'];
  isController: boolean;
}> = ({ guardian, isController }) => {
  const config = {
    permitting: { icon: '🛡️', label: 'ALLOWED', color: colors.success },
    warning: { icon: '⚠️', label: 'WARNING', color: colors.warning },
    blocking: { icon: '🚫', label: 'BLOCKED', color: colors.danger },
  }[guardian.status];
  
  return (
    <div style={rowStyle(isController, config.color)}>
      <span style={{ fontSize: '16px' }}>{config.icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: 500, color: colors.text, fontSize: '12px' }}>Guardian</span>
          <span style={{ 
            fontSize: '10px', 
            fontWeight: 600, 
            color: config.color,
            background: `${config.color}20`,
            padding: '1px 6px',
            borderRadius: '3px'
          }}>{config.label}</span>
        </div>
        {guardian.blockedBy && (
          <div style={{ fontSize: '11px', color: colors.danger, marginTop: '2px' }}>
            {guardian.blockedBy}
          </div>
        )}
      </div>
      {isController && (
        <span style={{ 
          fontSize: '9px', 
          fontWeight: 700, 
          color: colors.danger,
          background: `${colors.danger}20`,
          padding: '2px 6px',
          borderRadius: '3px'
        }}>BLOCKING</span>
      )}
    </div>
  );
};

// ============================================================================
// TRADING ROW
// ============================================================================

const TradingRow: React.FC<{ 
  trading: AuthorityState['trading'];
  isController: boolean;
  controlledBy: ControllingAuthority;
}> = ({ trading, isController, controlledBy }) => {
  const config = {
    active: { icon: '📈', label: 'ACTIVE', color: colors.success },
    paused: { icon: '⏸️', label: 'PAUSED', color: colors.warning },
    idle: { icon: '💤', label: 'IDLE', color: colors.muted },
  }[trading.intent];
  
  const badgeLabel = controlledBy === 'user' ? 'USER PAUSED' : 
                     isController ? 'IN CONTROL' : null;
  const badgeColor = controlledBy === 'user' ? colors.warning : colors.success;
  
  return (
    <div style={rowStyle(isController, config.color)}>
      <span style={{ fontSize: '16px' }}>{config.icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: 500, color: colors.text, fontSize: '12px' }}>Trading</span>
          <span style={{ 
            fontSize: '10px', 
            fontWeight: 600, 
            color: config.color,
            background: `${config.color}20`,
            padding: '1px 6px',
            borderRadius: '3px'
          }}>{config.label}</span>
        </div>
        {trading.pausedReason && (
          <div style={{ fontSize: '11px', color: colors.muted, marginTop: '2px' }}>
            {trading.pausedReason}
          </div>
        )}
      </div>
      {badgeLabel && (
        <span style={{ 
          fontSize: '9px', 
          fontWeight: 700, 
          color: badgeColor,
          background: `${badgeColor}20`,
          padding: '2px 6px',
          borderRadius: '3px'
        }}>{badgeLabel}</span>
      )}
    </div>
  );
};

// ============================================================================
// SUMMARY SECTION
// ============================================================================

const getSummary = (authority: AuthorityState, controlledBy: ControllingAuthority) => {
  switch (controlledBy) {
    case 'heartbeat':
      return {
        icon: '🔴',
        text: 'Trading STOPPED: System is down',
        color: colors.danger,
      };
    case 'guardian':
      return {
        icon: '🔴',
        text: `Trading FORBIDDEN: ${authority.guardian.blockedBy || 'Risk limit'}`,
        color: colors.danger,
      };
    case 'user':
      return {
        icon: '🟡',
        text: `Trading PAUSED: ${authority.trading.pausedReason || 'Manual hold'}`,
        color: colors.warning,
      };
    case 'trading':
      if (authority.trading.intent === 'idle') {
        return {
          icon: '⚪',
          text: 'Trading IDLE: No signals',
          color: colors.muted,
        };
      }
      return {
        icon: '🟢',
        text: 'Trading ACTIVE: Strategy in control',
        color: colors.success,
      };
  }
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const AuthorityPanel: React.FC<AuthorityPanelProps> = ({
  authority,
  controlledBy,
}) => {
  const summary = getSummary(authority, controlledBy);
  
  return (
    <div style={{
      background: colors.bg,
      border: `1px solid ${colors.border}`,
      borderRadius: '8px',
      padding: '12px',
    }}>
      {/* Authority Rows */}
      <HeartbeatRow 
        heartbeat={authority.heartbeat} 
        isController={controlledBy === 'heartbeat'}
      />
      <GuardianRow 
        guardian={authority.guardian} 
        isController={controlledBy === 'guardian'}
      />
      <TradingRow 
        trading={authority.trading} 
        isController={controlledBy === 'trading' || controlledBy === 'user'}
        controlledBy={controlledBy}
      />
      
      {/* Summary */}
      <div style={{
        marginTop: '8px',
        padding: '8px 10px',
        background: `${summary.color}10`,
        border: `1px solid ${summary.color}30`,
        borderRadius: '6px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
      }}>
        <span style={{ fontSize: '14px' }}>{summary.icon}</span>
        <span style={{ 
          fontSize: '12px', 
          fontWeight: 600, 
          color: summary.color 
        }}>{summary.text}</span>
      </div>
    </div>
  );
};

export default AuthorityPanel;
