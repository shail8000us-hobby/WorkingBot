import React, {
  useState,
  useEffect,
  useRef,
  useMemo,
  useCallback,
  Suspense
} from 'react';
import { Alert, Snackbar, CircularProgress } from '@mui/material';
import {
  LayoutDashboard,
  Layers3,
  ShieldCheck,
  SlidersHorizontal,
  Zap,
  BookOpen,
  RadioTower,
  PauseCircle,
  Terminal,
  Play,
  Square,
  RefreshCw,
  TrendingUp,
  Code,
  Activity,
  BarChart3,
  Brain
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';

// Week 2: Zustand store and data aggregator integration
import { dataAggregator } from './services/dataAggregator';
import { useStore, useStoreActions } from './store';

// Week 3: Feature flags and Guardian Dashboard
import { useFeatureFlag } from './utils/featureFlags';

import TopBar from './components/layout/TopBar';
import Sidebar from './components/layout/Sidebar';
import CollapsibleCard from './components/common/CollapsibleCard.tsx';
import { VolatilityRegimePanel, UnrealizedPnLPanel } from './components/panels';
import EmergencyKillButton from './components/EmergencyKillButton';
import TradingModeSwitch from './components/TradingModeSwitch';
import HealthCheckDashboard from './components/HealthCheckDashboard';
import EnhancedErrorBoundary from './components/EnhancedErrorBoundary';
import { userPreferences } from './utils/storage';
import { perfMonitor } from './utils/performanceMonitor';
import { useThemeMode } from './hooks/useThemeMode';
import { useSystemStatus } from './context/SystemStatusContext';
import { useBotControl } from './hooks/useBotControl';

// Phase 2: UI/UX Modernization - Import new styles
import './styles/animations.css';
import './styles/typography.css';
import './styles/micro-interactions.css';
import { useSocketConnection } from './hooks/useSocketConnection';
import { useConfigManager } from './hooks/useConfigManager';
import { useTradingData } from './hooks/useTradingData';
import { MobileOptimizationProvider } from './context/MobileOptimizationContext';
import { SymbolProvider } from './context/SymbolContext';
import { InstanceProvider } from './context/InstanceContext';
import IdleIndicator from './components/IdleIndicator';
import SafetyWarningBanner from './components/SafetyWarningBanner';
import OfflineIndicator from './components/OfflineIndicator';
import SymbolContextBar from './components/layout/SymbolContextBar';
import InstanceContextBar from './components/layout/InstanceContextBar';
// Mobile indicators removed for cleaner UI
// import MobileBatteryIndicator from './components/MobileBatteryIndicator';
// import TailscaleMobileOptimizer from './components/TailscaleMobileOptimizer';
import './App.css';

// Lazy load heavy components for better performance
const GuardianDashboard = React.lazy(() => import('./components/GuardianDashboard'));

// Lazy load heavy components for better initial load performance
const ConfigPanel = React.lazy(() => import('./components/ConfigPanel'));
const LogsPanel = React.lazy(() => import('./components/LogsPanel'));
const MonitoringPanel = React.lazy(() => import('./components/MonitoringPanel'));
const MonitoringDashboard = React.lazy(() => import('./components/MonitoringDashboard'));
const ProductionMonitoringDashboard = React.lazy(() => import('./components/ProductionMonitoringDashboard'));
const GuardianPanel = React.lazy(() => import('./components/GuardianPanel'));
const PM2Panel = React.lazy(() => import('./components/PM2Panel'));
const BotManagementDashboard = React.lazy(() => import('./components/BotManagement/BotManagementDashboard'));
const RobustnessPanel = React.lazy(() => import('./components/RobustnessPanel'));
const CapitalProtectionPanel = React.lazy(() => import('./components/CapitalProtectionPanel'));
const InstitutionalAIPanel = React.lazy(() => import('./components/InstitutionalAIPanel'));
const LiquidationProtectionPanel = React.lazy(() => import('./components/LiquidationProtectionPanel'));
const TradingStatusPanel = React.lazy(() => import('./components/TradingStatusPanel'));
const AIAdvisorWidget = React.lazy(() => import('./components/AIAdvisorWidget'));
const MarketNewsWidget = React.lazy(() => import('./components/MarketNewsWidget'));
const CommandKnowledgeBase = React.lazy(() => import('./components/CommandKnowledgeBase'));
const SyncReconciliationPanel = React.lazy(() => import('./components/SyncReconciliationPanel'));
const EmergencyControlsPanel = React.lazy(() => import('./components/EmergencyControlsPanel'));
const ErrorIntelligencePanel = React.lazy(() => import('./components/ErrorIntelligencePanel_simple'));
const ErrorIntelligenceLive = React.lazy(() => import('./components/ErrorIntelligenceLive'));
const ReconciliationPanelV2 = React.lazy(() => import('./components/ReconciliationPanelV2'));
const PositionsPanel = React.lazy(() => import('./components/PositionsPanel'));
const OptionsPanel = React.lazy(() => import('./components/options').then(m => ({ default: m.OptionsPanel })));
const OptionsChainPanel = React.lazy(() => import('./components/optionsChain').then(m => ({ default: m.OptionsChainPanel })));
const StrategyBuilder = React.lazy(() => import('./components/optionsStrategy').then(m => ({ default: m.StrategyBuilder })));
const MLInsightsPanel = React.lazy(() => import('./components/options/MLInsightsPanel'));
const MLStyleProfile = React.lazy(() => import('./components/options/MLStyleProfile'));
const MLOpportunityScanner = React.lazy(() => import('./components/options/MLOpportunityScanner'));
const MLDecisionCenter = React.lazy(() => import('./components/options/MLDecisionCenter'));
const MLModelMonitor = React.lazy(() => import('./components/options/MLModelMonitor'));
const DeltaTradeSync = React.lazy(() => import('./components/options/DeltaTradeSync'));
const MarketSignalPanel = React.lazy(() => import('./components/MarketSignalPanel'));
const ShutdownPanel = React.lazy(() => import('./components/ShutdownPanel'));
const OpportunisticRecoveryPanel = React.lazy(() => import('./components/OpportunisticRecoveryPanel'));
const BotActionsPanel = React.lazy(() => import('./components/BotActionsPanel'));
const BackendDownError = React.lazy(() => import('./components/BackendDownError'));
const TodoListPanel = React.lazy(() => import('./components/TodoListPanel'));
const BotBrainAnalyzer = React.lazy(() => import('./components/BotBrainAnalyzer'));
const FileEditor = React.lazy(() => import('./components/FileEditor'));
const StrategyEditor = React.lazy(() => import('./components/StrategyEditor'));
const FloatingPriceWidget = React.lazy(() => import('./components/FloatingPriceWidget'));
const ConfigVisualEditor = React.lazy(() => import('./components/ConfigVisualEditor'));
const ModeSwitcherPanel = React.lazy(() => import('./components/ModeSwitcherPanel'));
const SystemHealthPanel = React.lazy(() => import('./components/SystemHealthPanel'));
const MultiInstanceManager = React.lazy(() => import('./components/MultiInstanceManager'));
const MonitoringRecoveryPanel = React.lazy(() => import('./components/panels/MonitoringRecoveryPanel'));
const RSIPanel = React.lazy(() => import('./components/RSIPanel'));
const SymbolPortfolio = React.lazy(() => import('./components/SymbolPortfolio'));
const RiskSafetyDashboard = React.lazy(() => import('./components/RiskSafetyDashboard'));
const ZeroDTEDashboard = React.lazy(() => import('./components/zero_dte/ZeroDTEDashboard'));

const LoadingFallback = ({ message = 'Loading component...' }) => (
  <div className="flex items-center justify-center py-10 text-sm text-slate-400">
    <CircularProgress size={18} />
    <span className="ml-3">{message}</span>
  </div>
);

const MobileNav = ({ sections = [], activeSection, onSelect }) => (
  <div className="sticky top-[calc(9rem+env(safe-area-inset-top))] z-20 flex w-full gap-2 overflow-x-auto border-b border-slate-800/80 bg-slate-950/80 px-4 py-3 backdrop-blur lg:hidden">
    {sections.map(({ id, label }) => {
      const active = activeSection === id;
      return (
        <button
          key={id}
          type="button"
          onClick={() => onSelect?.(id)}
          className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-semibold transition ${
            active ? 'bg-sky-500 text-slate-900 shadow-card' : 'bg-slate-800/70 text-slate-300 hover:bg-slate-800'
          }`}
        >
          {label}
        </button>
      );
    })}
  </div>
);

function App() {
  const { mode, toggleMode } = useThemeMode();
  const {
    setSystemStatus,
    registerWarning,
    clearWarning,
    warnings: globalWarnings
  } = useSystemStatus();

  // UI State
  const [notification, setNotification] = useState({ open: false, message: '', severity: 'info' });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [backendDown, setBackendDown] = useState(false);
  const [connectionState, setConnectionState] = useState('disconnected');
  const [connectionQuality, setConnectionQuality] = useState('unknown');
  const [latencyStats, setLatencyStats] = useState({ avg: null, history: [] });
  const [featureFlags, setFeatureFlags] = useState({
    reconciliation_v2: false,
    reconciliation_v2_dry_run: true
  });
  const [activeSection, setActiveSection] = useState(userPreferences.selectedSection || 'dashboard');
  const [navParams, setNavParams] = useState(null); // Navigation params for section switches
  const [lastUpdated, setLastUpdated] = useState(null);
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.innerWidth < 768;
  });
  const [logs, setLogs] = useState([]);

  const latencyBufferRef = useRef([]);

  // Custom hooks for business logic
  const {
    tradingSnapshot,
    setTradingSnapshot,
    positionsData,
    setPositionsData,
    botStatus,
    setBotStatus,
    botIsRunning,
    openPositions,
    pendingOrders,
    totalPnl
  } = useTradingData();

  const {
    config,
    configMeta,
    setConfig,
    setConfigMeta,
    fetchInitialData,
    debouncedFetchInitialData,
    handleConfigUpdate
  } = useConfigManager({
    setBackendDown,
    setBotStatus,
    setTradingSnapshot,
    setPositionsData,
    setLogs,
    setFeatureFlags,
    setLastUpdated,
    setSystemStatus,
    setLoading,
    setBusy,
    showNotification: (message, severity) => setNotification({ open: true, message, severity }),
    globalWarnings,
    registerWarning,
    clearWarning
  });

  const connectionLatency = latencyStats.avg;

  useEffect(() => {
    setSystemStatus({
      botRunning: botIsRunning,
      lastSync: lastUpdated
    });
    if (!botIsRunning) {
      registerWarning({
        id: 'bot-stopped',
        type: 'bot',
        title: 'Bot is stopped',
        message: 'Start the bot to resume live metrics, PnL, and market monitoring.'
      });
    } else {
      clearWarning('bot-stopped');
    }
  }, [botIsRunning, lastUpdated, setSystemStatus, registerWarning, clearWarning]);

  useEffect(() => {
    perfMonitor.startTimer('app-initialization');
    return () => perfMonitor.endTimer('app-initialization');
  }, []);

  // Week 2: Start data aggregator on mount
  useEffect(() => {
    console.log('🚀 Starting data aggregator...');
    dataAggregator.start();
    
    // Cleanup: Stop data aggregator on unmount
    return () => {
      console.log('🛑 Stopping data aggregator...');
      dataAggregator.stop();
    };
  }, []); // Run once on mount

  useEffect(() => {
    userPreferences.selectedSection = activeSection;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [activeSection]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const showNotification = useCallback((message, severity = 'info') => {
    setNotification({ open: true, message, severity });
  }, []);

  const handleCloseNotification = useCallback(() => {
    setNotification((prev) => ({ ...prev, open: false }));
  }, []);

  const pushLatencySample = useCallback((latencyMs) => {
    if (latencyMs === null || latencyMs === undefined) {
      return;
    }
    const sample = {
      time: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      latency: Math.round(latencyMs)
    };
    latencyBufferRef.current = [...latencyBufferRef.current.slice(-59), sample];
    const avg = Math.round(
      latencyBufferRef.current.reduce((acc, item) => acc + Number(item.latency || 0), 0) /
      Math.max(latencyBufferRef.current.length, 1)
    );
    setLatencyStats({
      history: latencyBufferRef.current,
      avg
    });
  }, []);

  const ensureFresh = useCallback(() => {
    const manager = connectionManagerRef.current;
    if (!manager) {
      return;
    }
    if (manager.socket?.connected) {
      manager.socket.emit('request_full_state');
    } else {
      manager.forceReconnect();
    }
  }, []);

  const handleHardRefresh = useCallback(() => {
    showNotification('Hard refreshing dashboard...', 'info');
    setTimeout(() => window.location.reload(true), 300);
  }, [showNotification]);

  const handleClearCache = useCallback(async () => {
    try {
      showNotification('Clearing browser cache...', 'info');
      if (typeof caches !== 'undefined') {
        const cacheNames = await caches.keys();
        await Promise.all(cacheNames.map((name) => caches.delete(name)));
      }
      localStorage.clear();
      sessionStorage.clear();
      showNotification('Cache cleared. Reloading...', 'success');
      setTimeout(() => window.location.reload(true), 400);
    } catch (error) {
      showNotification(`Failed to clear cache: ${error.message}`, 'error');
    }
  }, [showNotification]);

  // Bot control hook
  const { handleStartBot, handleStopBot, handleRestartBot } = useBotControl({
    setBusy,
    showNotification: (message, severity) => setNotification({ open: true, message, severity }),
    onSuccess: debouncedFetchInitialData
  });

  // Socket connection hook
  const connectionManagerRef = useSocketConnection({
    config,
    setConfig,
    setConfigMeta,
    setBotStatus,
    setTradingSnapshot,
    setPositionsData,
    setLogs,
    setConnectionState,
    setConnectionQuality,
    setLastUpdated,
    showNotification: (message, severity) => setNotification({ open: true, message, severity }),
    pushLatencySample,
    debouncedFetchInitialData
  });

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        setTimeout(ensureFresh, 350);
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [ensureFresh]);

  useEffect(() => {
    const handleOnline = () => setTimeout(ensureFresh, 500);
    window.addEventListener('online', handleOnline);
    return () => window.removeEventListener('online', handleOnline);
  }, [ensureFresh]);

  useEffect(() => {
    const handleNotification = (event) => {
      showNotification(event.detail.message, event.detail.severity);
    };
    window.addEventListener('showNotification', handleNotification);
    return () => window.removeEventListener('showNotification', handleNotification);
  }, [showNotification]);

  useEffect(() => {
    const handleStart = () => handleStartBot();
    const handleStop = () => handleStopBot();
    const handleRefresh = () => ensureFresh();

    window.addEventListener('keyboard-start', handleStart);
    window.addEventListener('keyboard-stop', handleStop);
    window.addEventListener('keyboard-refresh', handleRefresh);

    return () => {
      window.removeEventListener('keyboard-start', handleStart);
      window.removeEventListener('keyboard-stop', handleStop);
      window.removeEventListener('keyboard-refresh', handleRefresh);
    };
  }, [handleStartBot, handleStopBot, ensureFresh]);

  // Initial data load - only run once on mount
  useEffect(() => {
    fetchInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty deps = run only once on mount

  // Week 3: Check guardian dashboard feature flag
  const { enabled: guardianEnabled } = useFeatureFlag('guardian_dashboard');

  const sections = useMemo(() => [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard,
      badge: pendingOrders ?? undefined,
      description: 'Trading overview & telemetry'
    },
    {
      id: 'portfolio',
      label: '📊 Portfolio',
      icon: TrendingUp,
      description: 'Multi-symbol overview - all symbols at a glance'
    },
    {
      id: 'config',
      label: 'Configuration',
      icon: SlidersHorizontal,
      description: 'Bot parameters and reconciliation tools'
    },
    {
      id: 'risk',
      label: 'Risk & Safety',
      icon: ShieldCheck,
      description: 'Risk analytics and protection systems'
    },
    {
      id: 'rsi',
      label: 'RSI',
      icon: BarChart3,
      description: 'RSI safety monitor - mode-specific thresholds with hysteresis'
    },
    {
      id: 'positions',
      label: 'Positions',
      icon: Layers3,
      badge: openPositions ?? undefined,
      description: 'Active grids & execution state'
    },
    {
      id: 'options',
      label: '📈 Options',
      icon: TrendingUp,
      description: 'Options trading - manage calls/puts positions'
    },
    {
      id: 'options_chain',
      label: '🔗 Options Chain',
      icon: BarChart3,
      description: 'Options chain - market data, IV, Greeks, strike selection'
    },
    {
      id: 'strategy_builder',
      label: '🏗️ Strategy Builder',
      icon: Layers3,
      description: 'Multi-leg options strategies - straddles, iron condors, spreads'
    },
    // Week 3: Guardian Dashboard (feature flag controlled)
    ...(guardianEnabled ? [{
      id: 'guardian',
      label: '🛡️ Guardian',
      icon: ShieldCheck,
      description: 'WebUI robustness monitor - circuit breakers, metrics, health'
    }] : []),
    {
      id: 'ml_trading',
      label: 'ML',
      icon: Brain,
      description: 'Machine Learning trading insights, style analysis, and autonomous decision engine'
    },
    {
      id: 'botmanagement',
      label: 'Bot Management',
      icon: Terminal,
      description: 'tmux control, process management, and emergency controls'
    },
    {
      id: 'actions',
      label: 'Bot Actions',
      icon: Zap,
      description: 'Real-time bot decisions and future intentions'
    },
    {
      id: 'brain_flow',
      label: 'Brain Flow Graph',
      icon: TrendingUp,
      description: 'Visual decision flowchart - see bot complete decision tree'
    },
    {
      id: 'intelligence',
      label: 'Intelligence',
      icon: BookOpen,
      description: 'AI insights, documentation, market intel'
    },
    {
      id: 'file_editor',
      label: 'File Editor',
      icon: Code,
      description: 'Edit code with AI assistance - syntax highlighting, templates, auto-backup'
    },
    {
      id: 'strategy_editor',
      label: 'Strategy Editor',
      icon: SlidersHorizontal,
      description: 'Visual strategy builder - templates, forms, comparison, backtest'
    },
    {
      id: 'config_visual_editor',
      label: 'Config Editor',
      icon: SlidersHorizontal,
      description: 'Edit configuration with forms or YAML - validation, diff, backups'
    },
    {
      id: 'mode_switcher',
      label: 'Mode Switcher',
      icon: RefreshCw,
      description: 'Auto LONG/SHORT switching - configure thresholds, manual override'
    },
    {
      id: 'system_health',
      label: 'System Health',
      icon: Activity,
      description: 'Real-time system monitoring - CPU, memory, disk, process health, alerts'
    },
    {
      id: 'instance_manager',
      label: 'Instance Manager',
      icon: Layers3,
      description: 'Run multiple bots simultaneously - demo + live, different strategies'
    },
    {
      id: 'todos',
      label: 'Todo List',
      icon: BookOpen,
      description: 'Track improvements and ideas for the trading bot'
    },
    {
      id: 'zero_dte',
      label: '⏱️ 0DTE Trading',
      icon: Zap,
      description: '0DTE options - autonomous strangle with premium balancing'
    }
  ], [openPositions, pendingOrders]);

  useEffect(() => {
    const handleKeyboardNav = (event) => {
      const index = event.detail;
      if (typeof index === 'number' && sections[index]) {
        setActiveSection(sections[index].id);
      }
    };
    window.addEventListener('keyboard-tab-change', handleKeyboardNav);
    return () => window.removeEventListener('keyboard-tab-change', handleKeyboardNav);
  }, [sections]);

  useEffect(() => {
    if (!sections.some((section) => section.id === activeSection) && sections.length > 0) {
      setActiveSection(sections[0].id);
    }
  }, [sections, activeSection]);

  const socket = connectionManagerRef.current?.socket;

  const renderInactivePanel = (title, message, cta = null) => (
    <div className="flex min-h-[200px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-700/70 bg-slate-900/40 p-6 text-center">
      <PauseCircle className="mb-3 h-10 w-10 text-slate-500" />
      <p className="text-sm font-semibold text-slate-200">{title}</p>
      <p className="mt-2 max-w-sm text-xs text-slate-400">{message}</p>
      {cta}
    </div>
  );

  const handleDeepLink = useCallback((tab) => {
    const map = {
      configuration: 'config',
      monitoring: 'monitoring',
      sync: 'monitoring',
      reconciliation: 'monitoring',
      guardian: 'risk',
      liquidation_monitor: 'risk',
      capital_protection: 'risk',
      risk_management: 'risk',
      emergency_controls: 'emergency',
      ai_advisor: 'intelligence',
      logs: 'monitoring',
      bot_management: 'monitoring',
      documentation: 'intelligence',
      positions: 'positions'
    };
    const sectionId = map[tab];
    if (sectionId) {
      setActiveSection(sectionId);
      showNotification(`Navigated to ${sectionId.replace('_', ' ')}`, 'info');
    }
  }, [showNotification]);
  // Navigation handler that clears params when navigating via sidebar
  const handleSectionSelect = useCallback((sectionId) => {
    setActiveSection(sectionId);
    // Clear nav params when navigating via normal sidebar click
    setNavParams(null);
  }, []);



  const renderActions = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="bot-actions"
        title="Bot Actions"
        subtitle="Real-time bot decisions, future intentions, and event stream"
        accent="cyan"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="BotActionsPanel">
          <BotActionsPanel />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );

  const renderTodos = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="todo-list"
        title="📝 Improvement Todo List"
        subtitle="Track your ideas and improvements for the trading bot"
        accent="amber"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="TodoListPanel">
          <TodoListPanel />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );

  const renderFileEditor = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="file-editor"
        title="💻 File Editor with AI"
        subtitle="Edit code files with AI assistance, syntax highlighting, templates, and auto-backup"
        accent="purple"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="FileEditor">
          <FileEditor />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );

  const renderStrategyEditor = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="strategy-editor"
        title="📊 Strategy Editor"
        subtitle="Visual strategy builder with templates, forms, comparison, and backtest capabilities"
        accent="blue"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="StrategyEditor">
          <StrategyEditor />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );

  const renderConfigVisualEditor = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="config-visual-editor"
        title="⚙️ Configuration Editor"
        subtitle="Edit configuration with forms or YAML - validation, diff preview, and auto-backup"
        accent="purple"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="ConfigVisualEditor">
          <ConfigVisualEditor />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );

  const renderModeSwitcher = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="mode-switcher"
        title="🔄 Auto Mode Switcher"
        subtitle="Automatic LONG/SHORT switching based on price - hysteresis, manual override, switch history"
        accent="cyan"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="ModeSwitcherPanel">
          <ModeSwitcherPanel />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );

  const renderSystemHealth = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="system-health"
        title="📊 System Health Monitor"
        subtitle="Real-time system monitoring - CPU, memory, disk, process health, API status, alerts with auto-healing"
        accent="green"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="SystemHealthPanel">
          <SystemHealthPanel />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );

  const renderInstanceManager = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="instance-manager"
        title="🤖 Multi-Instance Manager"
        subtitle="Run multiple bot instances simultaneously - demo + live, different strategies, independent control"
        accent="emerald"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="MultiInstanceManager">
          <MultiInstanceManager />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );

  const renderZeroDTE = () => (
    <div className="grid gap-6">
      <Suspense fallback={<LoadingFallback message="Loading 0DTE Dashboard..." />}>
        <EnhancedErrorBoundary componentName="ZeroDTEDashboard">
          <ZeroDTEDashboard />
        </EnhancedErrorBoundary>
      </Suspense>
    </div>
  );

  const renderBrainFlow = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="brain-flow"
        title="🧠 Bot Brain Decision Flow"
        subtitle="Visual flowchart showing complete decision tree"
        accent="purple"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="BotBrainAnalyzer">
          <BotBrainAnalyzer />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );

  const renderDashboard = () => (
    <div className="grid gap-6">
      {/* Bot Monitoring Dashboard - Top Priority */}
      <CollapsibleCard
        id="bot-monitoring-dashboard"
        title="🔍 Bot Monitoring Dashboard"
        subtitle="5-layer monitoring system: Price health, pre-order stats, TP verification, anomaly detection, and predictive actions"
        accent="purple"
        defaultOpen={!isMobile}
      >
        <Suspense fallback={<LoadingFallback message="Loading bot monitoring..." />}>
          <EnhancedErrorBoundary componentName="MonitoringDashboard">
            <MonitoringDashboard />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      {/* Volatility Chart - Full Width at Top */}
      <CollapsibleCard
        id="volatility-regime"
        title="Volatility Regime"
        subtitle="Comparing implied vs realized volatility"
        accent="violet"
        defaultOpen={!isMobile}
      >
        <VolatilityRegimePanel socket={socket} />
      </CollapsibleCard>

      {/* Market Signal Intelligence - Below Volatility */}
      <CollapsibleCard
        id="market-signal"
        title="Market Signal Intelligence"
        subtitle="Volatility regime, drift detection, and trade readiness"
        accent="violet"
        defaultOpen={!isMobile}
      >
        {botIsRunning ? (
          <Suspense fallback={<LoadingFallback message="Loading market insights..." />}>
            <EnhancedErrorBoundary componentName="MarketSignalPanel">
              <MarketSignalPanel />
            </EnhancedErrorBoundary>
          </Suspense>
        ) : (
          renderInactivePanel(
            'Market signal waiting for bot',
            'Once the bot subscribes to exchange feeds we will display readiness scores and drift analytics.'
          )
        )}
      </CollapsibleCard>

      {/* Unrealized PnL - Full Width */}
      <CollapsibleCard
        id="pnl-trend"
        title="Unrealized PnL Trend"
        subtitle="Intraday performance across trading session"
        accent="emerald"
        defaultOpen={!isMobile}
      >
        <UnrealizedPnLPanel socket={socket} />
      </CollapsibleCard>

      <CollapsibleCard
        id="runtime-health"
        title="Runtime Health & Connectivity"
        subtitle="Connectivity, safety, and backend signals"
        accent="emerald"
        defaultOpen={!isMobile}
      >
        <EnhancedErrorBoundary componentName="HealthCheckDashboard">
          <HealthCheckDashboard 
            socket={socket} 
            latencyStats={latencyStats}
            connectionQuality={connectionQuality}
            botIsRunning={botIsRunning}
          />
        </EnhancedErrorBoundary>
      </CollapsibleCard>

      <CollapsibleCard
        id="bot-status"
        title="Bot Runtime Status"
        subtitle="Process telemetry and trading mode"
        accent="sky"
        defaultOpen={!isMobile}
      >
        <div className="mt-6">
          <TradingModeSwitch botRunning={botIsRunning} />
        </div>
      </CollapsibleCard>

      {/* System Monitoring - Added to Dashboard */}
      <CollapsibleCard
        id="system-monitoring"
        title="System Monitoring"
        subtitle="Guardian daemons, watchdog status, and bot telemetry"
        accent="sky"
        defaultOpen={!isMobile}
      >
        {botIsRunning ? (
          <Suspense fallback={<LoadingFallback message="Loading monitoring dashboard..." />}>
            <EnhancedErrorBoundary componentName="MonitoringPanel">
              <MonitoringPanel 
                botStatus={botStatus}
                config={config}
                onNavigate={(section) => console.log('Navigate to:', section)}
              />
            </EnhancedErrorBoundary>
          </Suspense>
        ) : (
          renderInactivePanel(
            'Monitoring idle',
            'Process metrics and guardian heartbeat dashboards become available once services start.'
          )
        )}
      </CollapsibleCard>

      <CollapsibleCard
        id="monitoring-recovery-system"
        title="Monitoring & Recovery System"
        subtitle="Combined monitoring and recovery engine status"
        accent="emerald"
        defaultOpen={!isMobile}
      >
        <Suspense fallback={<LoadingFallback message="Loading monitoring & recovery..." />}>
          <EnhancedErrorBoundary componentName="MonitoringRecoveryPanel">
            <MonitoringRecoveryPanel />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      <CollapsibleCard
        id="production-monitoring"
        title="🔒 Production Monitoring"
        subtitle="Health, risk metrics, rate limits, and execution statistics"
        accent="purple"
        defaultOpen={!isMobile}
      >
        <Suspense fallback={<LoadingFallback message="Loading production monitoring..." />}>
          <EnhancedErrorBoundary componentName="ProductionMonitoringDashboard">
            <ProductionMonitoringDashboard />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>
    </div>
  );

  const renderPositions = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="positions-panel"
        title="Open Positions"
        subtitle="Real-time grid exposure and unrealized PnL"
        accent="emerald"
        defaultOpen={!isMobile}
      >
        {botIsRunning ? (
          <Suspense fallback={<LoadingFallback message="Loading positions..." />}>
            <EnhancedErrorBoundary componentName="PositionsPanel">
              <PositionsPanel />
            </EnhancedErrorBoundary>
          </Suspense>
        ) : (
          renderInactivePanel(
            'No positions until bot starts',
            'Position inventory and tranche breakdown appear here after the trading engine is online.'
          )
        )}
      </CollapsibleCard>
    </div>
  );

  // Options Trading Panel (Jan 2026)
  const renderOptions = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="options-panel"
        title="📈 Options Trading"
        subtitle="Manage options positions - Close or add to existing positions"
        accent="violet"
        defaultOpen={true}
      >
        <Suspense fallback={<LoadingFallback message="Loading options..." />}>
          <EnhancedErrorBoundary componentName="OptionsPanel">
            <OptionsPanel />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>
    </div>
  );

  // Options Chain Panel (Jan 2026) - Market Data Viewer
  const renderOptionsChain = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="options-chain-panel"
        title="🔗 Options Chain"
        subtitle="Live options chain - IV, Greeks, strike selection by expiry"
        accent="cyan"
        defaultOpen={true}
      >
        <Suspense fallback={<LoadingFallback message="Loading options chain..." />}>
          <EnhancedErrorBoundary componentName="OptionsChainPanel">
            <OptionsChainPanel 
              buildYourOwnMode={navParams?.buildYourOwnMode || false}
            />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>
    </div>
  );

  // Options Strategy Builder (Jan 2026) - Multi-leg strategy builder
  const renderStrategyBuilder = () => (
    <div className="grid gap-6">
      <Suspense fallback={<LoadingFallback message="Loading strategy builder..." />}>
        <EnhancedErrorBoundary componentName="StrategyBuilder">
          <StrategyBuilder 
            onNavigateToTab={(tabId, params) => {
              setActiveSection(tabId);
              // Store params for the target tab (e.g., buildYourOwnMode for Options Chain)
              if (params) {
                setNavParams(params);
              } else {
                setNavParams(null);
              }
            }}
          />
        </EnhancedErrorBoundary>
      </Suspense>
    </div>
  );

  const renderRSI = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="rsi-panel"
        title="📊 RSI Safety Monitor (Layer 6)"
        subtitle="Mode-specific RSI thresholds with hysteresis protection"
        accent="purple"
        defaultOpen={!isMobile}
      >
        <Suspense fallback={<LoadingFallback message="Loading RSI monitor..." />}>
          <EnhancedErrorBoundary componentName="RSIPanel">
            <RSIPanel />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>
    </div>
  );

  const renderRisk = () => (
    <div className="grid gap-6">
      {/* Modern Unified Risk & Safety Dashboard */}
      <CollapsibleCard
        id="risk-safety-dashboard"
        title="🛡️ Risk & Safety Control Center"
        subtitle="6-Layer Guardian Protection • Real-time Monitoring • Institutional Grade Safety"
        accent="sky"
        defaultOpen={true}
      >
        <Suspense fallback={<LoadingFallback message="Loading safety dashboard..." />}>
          <EnhancedErrorBoundary componentName="RiskSafetyDashboard">
            <RiskSafetyDashboard />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      {/* Legacy panels kept for detailed configuration */}
      <CollapsibleCard
        id="capital-protection"
        title="Capital Protection Configuration"
        subtitle="Detailed configuration for drawdown limits and safe operating envelope"
        accent="emerald"
        defaultOpen={false}
      >
        <Suspense fallback={<LoadingFallback message="Loading capital protection..." />}>
          <EnhancedErrorBoundary componentName="CapitalProtectionPanel">
            <CapitalProtectionPanel />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      <CollapsibleCard
        id="liquidation-monitor"
        title="Liquidation Monitor Details"
        subtitle="Detailed liquidation proximity and margin buffer analytics"
        accent="rose"
        defaultOpen={true}
      >
        <Suspense fallback={<LoadingFallback message="Loading liquidation monitor..." />}>
          <EnhancedErrorBoundary componentName="LiquidationProtectionPanel">
            <LiquidationProtectionPanel />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      <CollapsibleCard
        id="risk-intelligence"
        title="Risk Intelligence"
        subtitle="Error intelligence, anomaly detection, and live log parsing"
        accent="violet"
        defaultOpen={!isMobile}
      >
        {botIsRunning ? (
          <div className="flex gap-6 lg:grid-cols-2">
            <Suspense fallback={<LoadingFallback message="Loading risk intelligence..." />}>
              <EnhancedErrorBoundary componentName="ErrorIntelligencePanel">
                <ErrorIntelligencePanel />
              </EnhancedErrorBoundary>
            </Suspense>
            <Suspense fallback={<LoadingFallback message="Connecting live feed..." />}>
              <EnhancedErrorBoundary componentName="ErrorIntelligenceLive">
                <ErrorIntelligenceLive />
              </EnhancedErrorBoundary>
            </Suspense>
          </div>
        ) : (
          renderInactivePanel(
            'Error intelligence idle',
            'Live anomaly scanning requires real-time logs from the trading engine and guardian. Start the bot to resume stream analysis.'
          )
        )}
      </CollapsibleCard>

      <CollapsibleCard
        id="guardian-robustness"
        title="Guardian & Robustness"
        subtitle="Guardrail automation and system self-healing"
        accent="sky"
        defaultOpen={!isMobile}
      >
        <div className="space-y-6">
          <Suspense fallback={<LoadingFallback message="Loading robustness metrics..." />}>
            <EnhancedErrorBoundary componentName="RobustnessPanel">
              <RobustnessPanel />
            </EnhancedErrorBoundary>
          </Suspense>
          <Suspense fallback={<LoadingFallback message="Loading guardian status..." />}>
            <EnhancedErrorBoundary componentName="GuardianPanel">
              <GuardianPanel />
            </EnhancedErrorBoundary>
          </Suspense>
        </div>
      </CollapsibleCard>
    </div>
  );

  const renderConfig = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="config-panel"
        title="GridBot Configuration"
        subtitle="Edit, validate, and persist bot parameters"
        accent="sky"
        actions={
          <button
            type="button"
            onClick={handleClearCache}
            className="rounded-full border border-slate-600/60 px-3 py-1 text-xs font-semibold text-slate-200 transition hover:border-sky-400 hover:text-sky-200"
          >
            Clear Cache
          </button>
        }
        defaultOpen={!isMobile}
      >
        <Suspense fallback={<LoadingFallback message="Loading configuration..." />}>
          <EnhancedErrorBoundary componentName="ConfigPanel">
            <ConfigPanel
              config={config}
              meta={configMeta}
              onUpdate={handleConfigUpdate}
              loading={busy || loading}
            />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      <CollapsibleCard
        id="sync-reconciliation"
        title="Sync & Reconciliation"
        subtitle="Ensure bot, exchange, and ledger remain consistent"
        accent="emerald"
        defaultOpen={!isMobile}
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <Suspense fallback={<LoadingFallback message="Loading sync tools..." />}>
            <EnhancedErrorBoundary componentName="SyncReconciliationPanel">
              <SyncReconciliationPanel />
            </EnhancedErrorBoundary>
          </Suspense>
          <Suspense fallback={<LoadingFallback message="Loading reconciliation dashboard..." />}>
            <EnhancedErrorBoundary componentName="ReconciliationPanelV2">
              <ReconciliationPanelV2 featureFlags={featureFlags} />
            </EnhancedErrorBoundary>
          </Suspense>
        </div>
      </CollapsibleCard>
    </div>
  );

  const renderEmergency = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="emergency-controls"
        title="Emergency Controls"
        subtitle="Emergency stop flags, reset tools, and safety overrides"
        accent="rose"
        defaultOpen={!isMobile}
      >
        <Suspense fallback={<LoadingFallback message="Loading emergency controls..." />}>
          <EnhancedErrorBoundary componentName="EmergencyControlsPanel">
            <EmergencyControlsPanel />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      <CollapsibleCard
        id="shutdown-report"
        title="Graceful Shutdown Report"
        subtitle="Historical shutdown telemetry and cleanup outcomes"
        accent="amber"
        defaultOpen={!isMobile}
      >
        <Suspense fallback={<LoadingFallback message="Loading shutdown reports..." />}>
          <EnhancedErrorBoundary componentName="ShutdownPanel">
            <ShutdownPanel socket={socket} />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>
    </div>
  );

  const renderMonitoring = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="system-monitoring"
        title="System Monitoring"
        subtitle="Guardian daemons, watchdog status, and bot telemetry"
        accent="sky"
        defaultOpen={!isMobile}
      >
        {botIsRunning ? (
          <Suspense fallback={<LoadingFallback message="Loading monitoring dashboard..." />}>
            <EnhancedErrorBoundary componentName="MonitoringPanel">
              <MonitoringPanel 
                botStatus={botStatus}
                config={config}
                onNavigate={(section) => console.log('Navigate to:', section)}
              />
            </EnhancedErrorBoundary>
          </Suspense>
        ) : (
          renderInactivePanel(
            'Monitoring idle',
            'Process metrics and guardian heartbeat dashboards become available once services start.'
          )
        )}
      </CollapsibleCard>

      <CollapsibleCard
        id="monitoring-recovery-system"
        title="Monitoring & Recovery System"
        subtitle="Combined monitoring and recovery engine status"
        accent="emerald"
        defaultOpen={!isMobile}
      >
        <Suspense fallback={<LoadingFallback message="Loading monitoring & recovery..." />}>
          <EnhancedErrorBoundary componentName="MonitoringRecoveryPanel">
            <MonitoringRecoveryPanel />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>
    </div>
  );

  const renderIntelligence = () => (
    <div className="grid gap-6">
      <CollapsibleCard
        id="ai-insights"
        title="AI Advisor & Institutional Toolkit"
        subtitle="Continuous intelligence, incident analysis, and strategic guidance"
        accent="violet"
        defaultOpen={!isMobile}
      >
        {botIsRunning ? (
          <div className="flex flex-col gap-6 max-w-[1485px]">
            <Suspense fallback={<LoadingFallback message="Loading AI advisor..." />}>
              <EnhancedErrorBoundary componentName="AIAdvisorWidget">
                <AIAdvisorWidget />
              </EnhancedErrorBoundary>
            </Suspense>
            <Suspense fallback={<LoadingFallback message="Loading institutional AI tools..." />}>
              <EnhancedErrorBoundary componentName="InstitutionalAIPanel">
                <InstitutionalAIPanel />
              </EnhancedErrorBoundary>
            </Suspense>
          </div>
        ) : (
          renderInactivePanel(
            'AI Advisor paused',
            'AI-driven insights populate after the trading engine streams fresh telemetry and market states.'
          )
        )}
      </CollapsibleCard>

      <CollapsibleCard
        id="docs"
        title="Know Your Bot"
        subtitle="Mac terminal commands for starting, stopping, monitoring, and troubleshooting"
        accent="purple"
        defaultOpen={!isMobile}
      >
        <Suspense fallback={<LoadingFallback message="Loading commands..." />}>
          <EnhancedErrorBoundary componentName="CommandKnowledgeBase">
            <CommandKnowledgeBase />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      <CollapsibleCard
        id="market-intel"
        title="Market Intelligence"
        subtitle="Macro signals, latency-aware news, and quant feeds"
        accent="emerald"
        defaultOpen={!isMobile}
      >
        <Suspense fallback={<LoadingFallback message="Loading market intelligence..." />}>
          <EnhancedErrorBoundary componentName="MarketNewsWidget">
            <MarketNewsWidget />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>
    </div>
  );

  const renderMLTrading = () => (
    <div className="grid gap-6">
      {/* ML Trading Insights */}
      <CollapsibleCard
        id="ml-insights"
        title="ML Trading Insights"
        subtitle="Machine learning model performance, trade statistics, and pattern recognition"
        accent="purple"
        defaultOpen={true}
      >
        <Suspense fallback={<LoadingFallback message="Loading ML insights..." />}>
          <EnhancedErrorBoundary componentName="MLInsightsPanel">
            <MLInsightsPanel />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      {/* Trading Style Profile */}
      <CollapsibleCard
        id="ml-style-profile"
        title="Trading Style Profile"
        subtitle="AI-analyzed trading DNA and behavioral patterns"
        accent="violet"
        defaultOpen={true}
      >
        <Suspense fallback={<LoadingFallback message="Loading style profile..." />}>
          <EnhancedErrorBoundary componentName="MLStyleProfile">
            <MLStyleProfile />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      {/* Opportunity Scanner */}
      <CollapsibleCard
        id="ml-opportunity-scanner"
        title="Opportunity Scanner"
        subtitle="AI-detected trading opportunities with style matching"
        accent="emerald"
        defaultOpen={true}
      >
        <Suspense fallback={<LoadingFallback message="Loading opportunity scanner..." />}>
          <EnhancedErrorBoundary componentName="MLOpportunityScanner">
            <MLOpportunityScanner symbol={'BTCUSDT'} />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      {/* Decision Center */}
      <CollapsibleCard
        id="ml-decision-center"
        title="Decision Center"
        subtitle="Autonomous AI decision engine and approval queue"
        accent="cyan"
        defaultOpen={true}
      >
        <Suspense fallback={<LoadingFallback message="Loading decision center..." />}>
          <EnhancedErrorBoundary componentName="MLDecisionCenter">
            <MLDecisionCenter />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      {/* Model Monitor */}
      <CollapsibleCard
        id="ml-model-monitor"
        title="Model Monitor"
        subtitle="ML model drift detection and retraining status"
        accent="amber"
        defaultOpen={true}
      >
        <Suspense fallback={<LoadingFallback message="Loading model monitor..." />}>
          <EnhancedErrorBoundary componentName="MLModelMonitor">
            <MLModelMonitor />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      {/* Delta Exchange Trade Sync */}
      <CollapsibleCard
        id="delta-trade-sync"
        title="Delta Exchange Trade Sync"
        subtitle="Fetch and sync actual trades from Delta Exchange for accurate PnL/win rate"
        accent="indigo"
        defaultOpen={true}
      >
        <Suspense fallback={<LoadingFallback message="Loading Delta sync..." />}>
          <EnhancedErrorBoundary componentName="DeltaTradeSync">
            <DeltaTradeSync />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>
    </div>
  );

  const renderBotManagement = () => (
    <div className="grid gap-6">
      {/* PM2 Process Manager */}
      <CollapsibleCard
        id="pm2-control"
        title="PM2 Process Manager"
        subtitle="Production-ready process management for GridBot, Guardian, and Heartbeat"
        accent="emerald"
        defaultOpen={!isMobile}
      >
        <Suspense fallback={<LoadingFallback message="Loading PM2 status..." />}>
          <EnhancedErrorBoundary componentName="PM2Panel">
            <PM2Panel />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      {/* Bot Management Dashboard */}
      <CollapsibleCard
        id="bot-management-dashboard"
        title="Bot Management Dashboard"
        subtitle="High-level view of bot orchestration and services"
        accent="sky"
        defaultOpen={!isMobile}
      >
        <Suspense fallback={<LoadingFallback message="Loading bot management..." />}>
          <EnhancedErrorBoundary componentName="BotManagementDashboard">
            <BotManagementDashboard />
          </EnhancedErrorBoundary>
        </Suspense>
      </CollapsibleCard>

      {/* Live Logs Stream */}
      <CollapsibleCard
        id="live-logs-botmanagement"
        title="Live Logs Stream"
        subtitle="Real-time bot logs with filtering and export"
        accent="violet"
        defaultOpen={!isMobile}
      >
        {botIsRunning ? (
          <Suspense fallback={<LoadingFallback message="Streaming logs..." />}>
            <EnhancedErrorBoundary componentName="LogsPanel">
              <LogsPanel logs={logs} />
            </EnhancedErrorBoundary>
          </Suspense>
        ) : (
          renderInactivePanel(
            'Logs unavailable',
            'Start the bot to stream live logs from guardian and trading processes'
          )
        )}
      </CollapsibleCard>
    </div>
  );

  const sectionContent = {
    actions: renderActions(),
    todos: renderTodos(),
    file_editor: renderFileEditor(),
    strategy_editor: renderStrategyEditor(),
    config_visual_editor: renderConfigVisualEditor(),
    mode_switcher: renderModeSwitcher(),
    system_health: renderSystemHealth(),
    instance_manager: renderInstanceManager(),
    brain_flow: renderBrainFlow(),
    dashboard: renderDashboard(),
    portfolio: <SymbolPortfolio />,
    positions: renderPositions(),
    options: renderOptions(),  // Jan 2026: Options Trading Panel
    options_chain: renderOptionsChain(),  // Jan 2026: Options Chain Market Data
    strategy_builder: renderStrategyBuilder(),  // Jan 2026: Options Strategy Builder
    risk: renderRisk(),
    rsi: renderRSI(),
    config: renderConfig(),
    ml_trading: renderMLTrading(),  // Jan 2026: ML Trading Panel
    botmanagement: renderBotManagement(),
    emergency: renderEmergency(),
    intelligence: renderIntelligence(),
    // Week 3: Guardian Dashboard
    guardian: guardianEnabled ? (
      <div className="grid gap-6">
        <CollapsibleCard
          id="guardian-dashboard"
          title="🛡️ Guardian Dashboard"
          subtitle="WebUI Robustness Monitor - Circuit breakers, metrics, and health"
          accent="emerald"
          defaultOpen={true}
        >
          <Suspense fallback={<LoadingFallback message="Loading Guardian Dashboard..." />}>
            <EnhancedErrorBoundary componentName="GuardianDashboard">
              <GuardianDashboard />
            </EnhancedErrorBoundary>
          </Suspense>
        </CollapsibleCard>
      </div>
    ) : null,
    // 0DTE Autonomous Trading
    zero_dte: renderZeroDTE()
  };

  const activeContent = sectionContent[activeSection] || renderDashboard();

  // Show backend down error page if backend is not responding
  if (backendDown) {
    return <BackendDownError onRetry={fetchInitialData} />;
  }

  return (
    <InstanceProvider>
    <SymbolProvider>
      <MobileOptimizationProvider>
        <div className="relative min-h-screen bg-surface text-slate-100">
          {/* V6.0: Instance Context Bar - REMOVED: Confusing, instance selection should be in BotManagement only */}
          {/* <InstanceContextBar 
            status={{ running: botIsRunning }}
            pnl={{ total: totalPnl }}
          /> */}
          <TopBar
            mode={mode}
            onToggleTheme={toggleMode}
            onRefresh={handleHardRefresh}
            onEnsureFresh={ensureFresh}
            isMobile={isMobile}
            isOnline={connectionState === 'connected'}
            botIsRunning={botIsRunning}
            metrics={{
              running: botIsRunning,
              latency: connectionLatency,
              latencyQuality: connectionQuality,
              unrealizedPnl: totalPnl,
              lastUpdated
            }}
            processStatus={{
              guardianPid: botStatus?.guardian_health?.pid || null,
              tradingBotPid: botStatus?.pid || null,
              healthBotPid: botStatus?.heartbeat?.pid || null
            }}
            warnings={globalWarnings}
          />
      
          {/* Phase 2: Symbol Context Bar - Always visible below TopBar */}
          <SymbolContextBar 
            gridInfo={config?.grid}
            status={{ running: botIsRunning }}
            pnl={totalPnl ? { total: totalPnl } : null}
          />

      <Sidebar
        sections={sections}
        activeSection={activeSection}
        onSelect={handleSectionSelect}
      />

      <main className="pt-60 lg:pt-56 pb-[calc(7rem+env(safe-area-inset-bottom))]" style={{ marginTop: 'calc(env(safe-area-inset-top) + 8px)' }}>
        <MobileNav
          sections={sections}
          activeSection={activeSection}
          onSelect={handleSectionSelect}
        />
        <div className="w-full">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeSection}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.25, ease: 'easeInOut' }}
            >
              {activeContent}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>

      <Snackbar
        open={notification.open}
        autoHideDuration={5000}
        onClose={handleCloseNotification}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={handleCloseNotification}
          severity={notification.severity}
          sx={{ width: '100%' }}
        >
          {notification.message}
        </Alert>
      </Snackbar>

      <div className="pointer-events-none fixed inset-x-0 top-16 z-10 flex justify-center lg:pl-64">
        <span className="rounded-b-3xl border border-slate-800/40 bg-slate-900/60 px-4 py-1 text-xs font-semibold uppercase tracking-widest text-slate-500">
          Connection: {connectionState} · Quality: {connectionQuality}
        </span>
      </div>

      {/* Idle Mode Indicator */}
      <IdleIndicator />
      
      {/* Offline Mode Indicator */}
      <OfflineIndicator />
      
      {/* Safety Warning - Shows bots are still running */}
      <SafetyWarningBanner />
      
      {/* Mobile indicators removed for cleaner mobile UI */}
      {/* <MobileBatteryIndicator /> */}
      {/* <TailscaleMobileOptimizer /> */}
      
      {/* Floating Price Widget - Real-time BTC/ETH prices */}
      <Suspense fallback={null}>
        <FloatingPriceWidget />
      </Suspense>
        </div>
      </MobileOptimizationProvider>
    </SymbolProvider>
    </InstanceProvider>
  );
}

export default App;
