/**
 * GridBot WebUI v2.0 - Main Application
 * 
 * Entry point that composes:
 * 1. Sidebar navigation (left)
 * 2. Global Control Plane (top, always visible)
 * 3. Section content based on active section
 */

import React, { useEffect, useState } from 'react';
import { GlobalControlPlane } from './components/GlobalControlPlane/GlobalControlPlane';
import { InstrumentGrid } from './components/InstrumentGrid/InstrumentGrid';
import { FocusView } from './components/FocusView/FocusView';
import { Sidebar, SectionId } from './components/Sidebar/Sidebar';
import { PositionsPanel } from './components/PositionsPanel/PositionsPanel';
import { LogsPanel } from './components/LogsPanel/LogsPanel';
import { BotManagementPanel } from './components/BotManagementPanel/BotManagementPanel';
import { SystemHealthPanel } from './components/SystemHealthPanel/SystemHealthPanel';
import { ConfigPanel } from './components/ConfigPanel/ConfigPanel';
import { RSIPanel } from './components/RSIPanel/RSIPanel';
import { IntelligencePanel } from './components/IntelligencePanel/IntelligencePanel';
import { GuardianPanel } from './components/GuardianPanel/GuardianPanel';
import { BotActionsPanel } from './components/BotActionsPanel/BotActionsPanel';
import { TodoListPanel } from './components/TodoListPanel/TodoListPanel';
import { FileEditorPanel } from './components/FileEditorPanel/FileEditorPanel';
import { ModeSwitcherPanel } from './components/ModeSwitcherPanel/ModeSwitcherPanel';
import { InstanceManagerPanel } from './components/InstanceManagerPanel/InstanceManagerPanel';
import { EmergencyControlsPanel } from './components/EmergencyControlsPanel/EmergencyControlsPanel';
import { PortfolioPanel } from './components/PortfolioPanel/PortfolioPanel';
import { MonitoringDashboard } from './components/MonitoringDashboard/MonitoringDashboard';
import { GridLevelChart } from './components/GridLevelChart/GridLevelChart';
import { ReconciliationPanel } from './components/ReconciliationPanel/ReconciliationPanel';
import { PnLChart } from './components/PnLChart/PnLChart';
import { VolatilityChart } from './components/VolatilityChart/VolatilityChart';
import { RiskSafetyDashboard } from './components/RiskSafetyDashboard/RiskSafetyDashboard';
import { BotBrainAnalyzer } from './components/BotBrainAnalyzer';
import { InstanceProvider } from './contexts/InstanceContext';
import { useGlobalStore } from './stores/globalStore';
import { connectInstrument, disconnectAll } from './services/websocket';
import { listInstances, getSystemHealth } from './services/api';
import { dataAggregator } from './services/dataAggregator';
import type { InstanceId } from './types';
import './styles/variables.css';
import './styles/global.css';

// ============================================================================
// INITIALIZATION HOOK
// ============================================================================

const useAppInitialization = () => {
  const setInstances = useGlobalStore((s) => s.setInstances);
  const registerInstance = useGlobalStore((s) => s.registerInstance);
  const updateSystemHealth = useGlobalStore((s) => s.updateSystemHealth);
  
  useEffect(() => {
    // Initial fetch of instances
    const fetchInstances = async () => {
      const response = await listInstances();
      if (response.success && response.data) {
        const instanceIds = response.data.map((i) => i.instanceId as InstanceId);
        setInstances(instanceIds);
        
        // Register each instance and connect websocket
        instanceIds.forEach((id) => {
          registerInstance(id);
          connectInstrument(id);
        });

        // Start data aggregator after instances are registered
        dataAggregator.start();
      }
    };
    
    // Initial health check
    const checkHealth = async () => {
      const response = await getSystemHealth();
      if (response.success && response.data) {
        updateSystemHealth(response.data);
      }
    };
    
    fetchInstances();
    checkHealth();
    
    // Cleanup on unmount
    return () => {
      dataAggregator.stop();
      disconnectAll();
    };
  }, [setInstances, registerInstance, updateSystemHealth]);
};

// ============================================================================
// MAIN APP COMPONENT
// ============================================================================

export const App: React.FC = () => {
  const viewMode = useGlobalStore((s) => s.viewMode);
  const sidebarCollapsed = useGlobalStore((s) => s.sidebarCollapsed);
  const [activeSection, setActiveSection] = useState<SectionId>('dashboard');
  
  useAppInitialization();

  // Render section content based on active section
  const renderSectionContent = () => {
    // If in focus mode, always show FocusView
    if (viewMode === 'focus') {
      return <FocusView />;
    }

    switch (activeSection) {
      case 'dashboard':
        return <InstrumentGrid />;
      case 'portfolio':
        return <PortfolioPanel />;
      case 'positions':
        return <PositionsPanel />;
      case 'logs':
        return <LogsPanel />;
      case 'botmanagement':
        return <BotManagementPanel />;
      case 'guardian':
        return <GuardianPanel />;
      case 'actions':
        return <BotActionsPanel />;
      case 'emergency':
        return <EmergencyControlsPanel />;
      case 'mode_switcher':
        return <ModeSwitcherPanel />;
      case 'systemhealth':
        return <SystemHealthPanel />;
      case 'config':
        return <ConfigPanel />;
      case 'file_editor':
        return <FileEditorPanel />;
      case 'instance_manager':
        return <InstanceManagerPanel />;
      case 'todos':
        return <TodoListPanel />;
      case 'rsi':
        return <RSIPanel />;
      case 'intelligence':
        return <IntelligencePanel />;
      case 'monitoring':
        return <MonitoringDashboard />;
      case 'gridchart':
        return <GridLevelChart />;
      case 'reconciliation':
        return <ReconciliationPanel />;
      case 'pnlchart':
        return <PnLChart />;
      case 'volatility':
        return <VolatilityChart />;
      case 'risksafety':
        return <RiskSafetyDashboard />;
      case 'brain':
        return <BotBrainAnalyzer />;
      default:
        return <InstrumentGrid />;
    }
  };
  
  return (
    <InstanceProvider>
      <div className="app-layout">
        {/* Sidebar Navigation */}
        <Sidebar 
          activeSection={activeSection} 
          onSectionChange={setActiveSection} 
        />
        
        {/* Main Content Area */}
        <div 
          className="app-content"
          style={{ marginLeft: sidebarCollapsed ? '60px' : '240px' }}
        >
          {/* Global Control Plane - NEVER scrolls away */}
          <GlobalControlPlane />
          
          {/* Section content */}
          <main className="app-main">
            {renderSectionContent()}
          </main>
        </div>
      </div>
    </InstanceProvider>
  );
};

export default App;
