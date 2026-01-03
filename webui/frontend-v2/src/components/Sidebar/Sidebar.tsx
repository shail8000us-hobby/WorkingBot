/**
 * Sidebar Navigation Component
 * 
 * Provides navigation between different sections of the v2 WebUI.
 * Matches features from v1 while using new architecture.
 */

import React from 'react';
import { useGlobalStore } from '../../stores/globalStore';
import styles from './Sidebar.module.css';

export type SectionId = 
  | 'dashboard'
  | 'portfolio'
  | 'positions'
  | 'logs'
  | 'config'
  | 'botmanagement'
  | 'guardian'
  | 'actions'
  | 'emergency'
  | 'rsi'
  | 'mode_switcher'
  | 'file_editor'
  | 'instance_manager'
  | 'todos'
  | 'systemhealth'
  | 'intelligence'
  | 'monitoring'
  | 'gridchart'
  | 'reconciliation'
  | 'pnlchart'
  | 'volatility'
  | 'risksafety'
  | 'brain';

interface SidebarSection {
  id: SectionId;
  label: string;
  icon: string;
  description: string;
  category?: 'main' | 'trading' | 'tools' | 'system';
}

const sections: SidebarSection[] = [
  // Main Section
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: '📊',
    description: 'Trading overview & instruments',
    category: 'main'
  },
  {
    id: 'portfolio',
    label: 'Portfolio',
    icon: '💼',
    description: 'Multi-symbol overview',
    category: 'main'
  },
  {
    id: 'positions',
    label: 'Positions',
    icon: '📈',
    description: 'Active positions & orders',
    category: 'main'
  },
  // Trading Section
  {
    id: 'botmanagement',
    label: 'Bot Control',
    icon: '🤖',
    description: 'Start/stop, process management',
    category: 'trading'
  },
  {
    id: 'guardian',
    label: 'Guardian',
    icon: '🛡️',
    description: 'Health monitoring & circuit breakers',
    category: 'trading'
  },
  {
    id: 'actions',
    label: 'Bot Actions',
    icon: '⚡',
    description: 'Real-time decisions & events',
    category: 'trading'
  },
  {
    id: 'emergency',
    label: 'Emergency',
    icon: '🚨',
    description: 'Emergency controls & kill switches',
    category: 'trading'
  },
  {
    id: 'mode_switcher',
    label: 'Mode Switcher',
    icon: '🔄',
    description: 'LONG/SHORT mode control',
    category: 'trading'
  },
  {
    id: 'rsi',
    label: 'RSI Monitor',
    icon: '📉',
    description: 'RSI thresholds & alerts',
    category: 'trading'
  },
  // Tools Section
  {
    id: 'config',
    label: 'Config',
    icon: '⚙️',
    description: 'Bot configuration',
    category: 'tools'
  },
  {
    id: 'file_editor',
    label: 'File Editor',
    icon: '📄',
    description: 'Edit config & strategy files',
    category: 'tools'
  },
  {
    id: 'instance_manager',
    label: 'Instances',
    icon: '📦',
    description: 'Multi-instance management',
    category: 'tools'
  },
  {
    id: 'todos',
    label: 'Todo List',
    icon: '✅',
    description: 'Improvements & task tracking',
    category: 'tools'
  },
  {
    id: 'logs',
    label: 'Logs',
    icon: '📝',
    description: 'Live log streaming',
    category: 'tools'
  },
  // System Section
  {
    id: 'systemhealth',
    label: 'System Health',
    icon: '💻',
    description: 'CPU, memory, disk',
    category: 'system'
  },
  {
    id: 'monitoring',
    label: 'Monitoring',
    icon: '📡',
    description: '5-layer monitoring dashboard',
    category: 'system'
  },
  {
    id: 'gridchart',
    label: 'Grid Chart',
    icon: '📊',
    description: 'Visual grid level chart',
    category: 'system'
  },
  {
    id: 'reconciliation',
    label: 'Reconciliation',
    icon: '🔍',
    description: 'Position & order sync',
    category: 'system'
  },
  {
    id: 'pnlchart',
    label: 'PnL Chart',
    icon: '💰',
    description: 'Historical PnL visualization',
    category: 'system'
  },
  {
    id: 'volatility',
    label: 'Volatility',
    icon: '🌊',
    description: 'IV vs RV monitoring',
    category: 'system'
  },
  {
    id: 'risksafety',
    label: 'Risk Safety',
    icon: '🔐',
    description: '6-layer protection status',
    category: 'system'
  },
  {
    id: 'brain',
    label: 'Bot Brain',
    icon: '🧠',
    description: 'Decision flow analyzer',
    category: 'system'
  },
  {
    id: 'intelligence',
    label: 'Intelligence',
    icon: '💡',
    description: 'AI insights & docs',
    category: 'system'
  }
];

interface SidebarProps {
  activeSection: SectionId;
  onSectionChange: (section: SectionId) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeSection, onSectionChange }) => {
  const sidebarCollapsed = useGlobalStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useGlobalStore((s) => s.toggleSidebar);

  return (
    <aside className={styles.sidebar} data-collapsed={sidebarCollapsed}>
      <div className={styles.header}>
        <h1 className={styles.logo}>
          {sidebarCollapsed ? '⚡' : '⚡ GridBot v2'}
        </h1>
        <button 
          className={styles.collapseButton}
          onClick={toggleSidebar}
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed ? '→' : '←'}
        </button>
      </div>

      <nav className={styles.nav}>
        {sections.map((section) => (
          <button
            key={section.id}
            className={styles.navItem}
            data-active={activeSection === section.id}
            onClick={() => onSectionChange(section.id)}
            title={sidebarCollapsed ? section.label : undefined}
          >
            <span className={styles.navIcon}>{section.icon}</span>
            {!sidebarCollapsed && (
              <span className={styles.navLabel}>{section.label}</span>
            )}
          </button>
        ))}
      </nav>

      <div className={styles.footer}>
        {!sidebarCollapsed && (
          <span className={styles.version}>v2.0.0</span>
        )}
      </div>
    </aside>
  );
};

export default Sidebar;
