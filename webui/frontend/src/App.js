import React, { useState, useEffect, useRef, useMemo, useCallback, Suspense, startTransition } from 'react';
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
  Brain,
  Database,
  // Phase 1: Deduplicated navigation icons
  PieChart,
  Table2,
  Workflow,
  Scale,
  Coins,
  Timer,
  ListChecks,
  CandlestickChart,
} from 'lucide-react';
// framer-motion AnimatePresence removed: replaced with CSS for instant panel switches

// Week 2: Zustand store and data aggregator integration
import { dataAggregator } from './services/dataAggregator';
import { useStore, useStoreActions } from './store';

// Week 3: Feature flags and Guardian Dashboard
import { useFeatureFlag } from './utils/featureFlags.ts';

import TopBar from './components/layout/TopBar';
import Sidebar from './components/layout/Sidebar';
import CollapsibleCard from './components/common/CollapsibleCard.tsx';
import PanelSkeleton from './components/common/PanelSkeleton';
import { VolatilityRegimePanel, UnrealizedPnLPanel } from './components/panels';
import EmergencyKillButton from './components/EmergencyKillButton';
import TradingModeSwitch from './components/TradingModeSwitch';
import EnhancedErrorBoundary from './components/EnhancedErrorBoundary';
import { userPreferences } from './utils/storage.ts';
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
import { AutoloopProvider } from './context/AutoloopContext';
import AutoloopStatusBar from './components/positionAdjustment/AutoloopStatusBar';
import IdleIndicator from './components/IdleIndicator';
import SafetyWarningBanner from './components/SafetyWarningBanner';
import OfflineIndicator from './components/OfflineIndicator';
// BackendDownError must NOT be lazy-loaded — it's the error fallback for backend failures
// and must be available immediately (lazy components need Suspense which may not be ready)
import BackendDownError from './components/BackendDownError';
import SymbolContextBar from './components/layout/SymbolContextBar';
import InstanceContextBar from './components/layout/InstanceContextBar';
// SSRAlgoErrorBoundary imported directly (class component can't be lazy loaded)
import { SSRAlgoErrorBoundary } from './components/ssrAlgo';
// MMMErrorBoundary + MMMProvider imported directly (class component can't be lazy loaded)
import { MMMErrorBoundary, MMMProvider } from './components/mmm';
// Mobile indicators removed for cleaner UI
// import MobileBatteryIndicator from './components/MobileBatteryIndicator';
// import TailscaleMobileOptimizer from './components/TailscaleMobileOptimizer';
import './App.css';

// Lazy load HealthCheckDashboard - only needed when health tab is visible
const HealthCheckDashboard = React.lazy(() => import('./components/HealthCheckDashboard'));

// Lazy load heavy components for better performance
const GuardianDashboard = React.lazy(() => import('./components/GuardianDashboard'));

// Lazy load heavy components for better initial load performance
// Using dynamic import with preload support for instant panel switches
const ConfigPanel = React.lazy(() => import('./components/ConfigPanel'));
const LogsPanel = React.lazy(() => import('./components/LogsPanel'));
const MonitoringPanel = React.lazy(() => import('./components/MonitoringPanel'));
const MonitoringDashboard = React.lazy(() => import('./components/MonitoringDashboard'));
const ProductionMonitoringDashboard = React.lazy(
  () => import('./components/ProductionMonitoringDashboard')
);
const GuardianPanel = React.lazy(() => import('./components/GuardianPanel'));
const PM2Panel = React.lazy(() => import('./components/PM2Panel'));
const BotManagementDashboard = React.lazy(
  () => import('./components/BotManagement/BotManagementDashboard')
);
const RobustnessPanel = React.lazy(() => import('./components/RobustnessPanel'));
const CapitalProtectionPanel = React.lazy(() => import('./components/CapitalProtectionPanel'));
const InstitutionalAIPanel = React.lazy(() => import('./components/InstitutionalAIPanel'));
const LiquidationProtectionPanel = React.lazy(
  () => import('./components/LiquidationProtectionPanel')
);
const TradingStatusPanel = React.lazy(() => import('./components/TradingStatusPanel'));
const AIAdvisorWidget = React.lazy(() => import('./components/AIAdvisorWidget'));
const MarketNewsWidget = React.lazy(() => import('./components/MarketNewsWidget'));
const CommandKnowledgeBase = React.lazy(() => import('./components/CommandKnowledgeBase'));
const SyncReconciliationPanel = React.lazy(() => import('./components/SyncReconciliationPanel'));
const EmergencyControlsPanel = React.lazy(() => import('./components/EmergencyControlsPanel'));
const ErrorIntelligencePanel = React.lazy(
  () => import('./components/ErrorIntelligencePanel_simple')
);
const ErrorIntelligenceLive = React.lazy(() => import('./components/ErrorIntelligenceLive'));
const ReconciliationPanelV2 = React.lazy(() => import('./components/ReconciliationPanelV2'));
const PositionsPanel = React.lazy(() => import('./components/PositionsPanel'));
const OptionsPanel = React.lazy(() =>
  import('./components/options').then((m) => ({ default: m.OptionsPanel }))
);
const OptionsChainPanel = React.lazy(() =>
  import('./components/optionsChain').then((m) => ({ default: m.OptionsChainPanel }))
);
const StrategyBuilder = React.lazy(() =>
  import('./components/optionsStrategy').then((m) => ({ default: m.StrategyBuilder }))
);
const MLInsightsPanel = React.lazy(() => import('./components/options/MLInsightsPanel'));
const MLStyleProfile = React.lazy(() => import('./components/options/MLStyleProfile'));
const MLOpportunityScanner = React.lazy(() => import('./components/options/MLOpportunityScanner'));
const MLDecisionCenter = React.lazy(() => import('./components/options/MLDecisionCenter'));
const MLModelMonitor = React.lazy(() => import('./components/options/MLModelMonitor'));
const DeltaTradeSync = React.lazy(() => import('./components/options/DeltaTradeSync'));
const MarketSignalPanel = React.lazy(() => import('./components/MarketSignalPanel'));
const ShutdownPanel = React.lazy(() => import('./components/ShutdownPanel'));
const OpportunisticRecoveryPanel = React.lazy(
  () => import('./components/OpportunisticRecoveryPanel')
);
const TodoListPanel = React.lazy(() => import('./components/TodoListPanel'));
const FloatingPriceWidget = React.lazy(() => import('./components/FloatingPriceWidget'));
const SystemHealthPanel = React.lazy(() => import('./components/SystemHealthPanel'));
const MonitoringRecoveryPanel = React.lazy(
  () => import('./components/panels/MonitoringRecoveryPanel')
);
const RSIPanel = React.lazy(() => import('./components/RSIPanel'));
const SymbolPortfolio = React.lazy(() => import('./components/SymbolPortfolio'));
const RiskSafetyDashboard = React.lazy(() => import('./components/RiskSafetyDashboard'));
const TradingViewSignals = React.lazy(() => import('./components/TradingViewSignals'));
const ZeroDTEDashboard = React.lazy(() => import('./components/zero_dte/ZeroDTEDashboard'));
const MVStraddlePanel = React.lazy(() => import('./components/mvStraddle/MVStraddlePanel'));
const ExperimentalPanel = React.lazy(() => import('./components/ExperimentalPanel'));
const AdvancedFeaturesPanel = React.lazy(() => import('./components/AdvancedFeaturesPanel'));
const SSRAlgoDashboard = React.lazy(() =>
  import('./components/ssrAlgo').then((m) => ({ default: m.SSRAlgoDashboard }))
);
const MMMDashboard = React.lazy(() =>
  import('./components/mmm').then((m) => ({ default: m.MMMDashboard }))
);

// Smart preloader: maps section IDs to their dynamic imports
// Only loads what's needed (adjacent tabs), NOT everything at once
const sectionImports = {
  dashboard: [() => import('./components/MonitoringDashboard'), () => import('./components/MonitoringPanel')],
  portfolio: [() => import('./components/SymbolPortfolio')],
  config: [() => import('./components/ConfigPanel'), () => import('./components/SyncReconciliationPanel')],
  risk: [() => import('./components/RiskSafetyDashboard'), () => import('./components/RobustnessPanel')],
  tradingview: [() => import('./components/TradingViewSignals')],
  rsi: [() => import('./components/RSIPanel')],
  positions: [() => import('./components/PositionsPanel')],
  options: [() => import('./components/options')],
  options_chain: [() => import('./components/optionsChain')],
  strategy_builder: [() => import('./components/optionsStrategy')],
  mv_straddle: [() => import('./components/mvStraddle/MVStraddlePanel')],
  mmm: [() => import('./components/mmm')],
  ssr_algo: [() => import('./components/ssrAlgo')],
  ml_trading: [() => import('./components/options/MLInsightsPanel')],
  botmanagement: [() => import('./components/BotManagement/BotManagementDashboard'), () => import('./components/PM2Panel')],
  intelligence: [() => import('./components/AIAdvisorWidget')],
  system_health: [() => import('./components/SystemHealthPanel')],
  todos: [() => import('./components/TodoListPanel')],
  zero_dte: [() => import('./components/zero_dte/ZeroDTEDashboard')],
  experimental: [() => import('./components/ExperimentalPanel')],
  advanced_features: [() => import('./components/AdvancedFeaturesPanel')],
};

// Preload adjacent sections only — called when active section changes
const preloadedSections = new Set();
const preloadAdjacentSections = (activeSectionId, sectionsList) => {
  const idx = sectionsList.findIndex(s => s.id === activeSectionId);
  if (idx === -1) return;
  // Preload prev and next sections
  const adjacentIds = [
    sectionsList[idx - 1]?.id,
    sectionsList[idx + 1]?.id,
  ].filter(Boolean);
  adjacentIds.forEach(id => {
    if (!preloadedSections.has(id) && sectionImports[id]) {
      preloadedSections.add(id);
      sectionImports[id].forEach(importFn => importFn().catch(() => { }));
    }
  });
};

const LoadingFallback = ({ message = 'Loading component...' }) => (
  <div className="flex items-center justify-center py-10 text-sm text-slate-400">
    <CircularProgress size={18} />
    <span className="ml-3">{message}</span>
  </div>
);

const MobileNav = ({ sections = [], activeSection, onSelect }) => {
  // Build grouped structure for mobile nav
  const groups = [];
  let currentGroup = null;
  sections.forEach((section) => {
    const group = section.group || 'Other';
    if (group !== currentGroup) {
      groups.push({ group, items: [section] });
      currentGroup = group;
    } else {
      groups[groups.length - 1].items.push(section);
    }
  });

  return (
    <div className="sticky top-[calc(9rem+env(safe-area-inset-top))] z-20 flex w-full items-center gap-1.5 overflow-x-auto border-b border-slate-800/80 bg-slate-950/80 px-4 py-3 backdrop-blur lg:hidden">
      {groups.map((g, gi) => (
        <React.Fragment key={g.group}>
          {gi > 0 && (
            <div className="mx-1 h-6 w-px shrink-0 bg-slate-700/60" />
          )}
          {g.items.map(({ id, label }) => {
            const active = activeSection === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => onSelect?.(id)}
                className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-semibold transition ${active
                  ? 'bg-sky-500 text-slate-900 shadow-card'
                  : 'bg-slate-800/70 text-slate-300 hover:bg-slate-800'
                  }`}
              >
                {label}
              </button>
            );
          })}
        </React.Fragment>
      ))}
    </div>
  );
};

function App() {
  const { mode, toggleMode } = useThemeMode();
  const {
    setSystemStatus,
    registerWarning,
    clearWarning,
    warnings: globalWarnings,
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
    reconciliation_v2_dry_run: true,
  });
  const [activeSection, setActiveSection] = useState(
    userPreferences.selectedSection || 'options'
  );
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
    totalPnl,
  } = useTradingData();

  const {
    config,
    configMeta,
    setConfig,
    setConfigMeta,
    fetchInitialData,
    debouncedFetchInitialData,
    handleConfigUpdate,
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
    clearWarning,
  });

  const connectionLatency = latencyStats.avg;

  useEffect(() => {
    setSystemStatus({
      botRunning: botIsRunning,
      lastSync: lastUpdated,
    });
    if (!botIsRunning) {
      registerWarning({
        id: 'bot-stopped',
        type: 'bot',
        title: 'Bot is stopped',
        message: 'Start the bot to resume live metrics, PnL, and market monitoring.',
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
      time: new Date().toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }),
      latency: Math.round(latencyMs),
    };
    latencyBufferRef.current = [...latencyBufferRef.current.slice(-59), sample];
    const avg = Math.round(
      latencyBufferRef.current.reduce((acc, item) => acc + Number(item.latency || 0), 0) /
      Math.max(latencyBufferRef.current.length, 1)
    );
    setLatencyStats({
      history: latencyBufferRef.current,
      avg,
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
    onSuccess: debouncedFetchInitialData,
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
    debouncedFetchInitialData,
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

  const sections = useMemo(
    () => [
      // ── Grid Bot ──────────────────────────────────────────────
      {
        id: 'dashboard',
        label: 'Dashboard',
        icon: LayoutDashboard,
        badge: pendingOrders ?? undefined,
        description: 'Trading overview & telemetry',
        group: 'Grid Bot',
      },
      {
        id: 'portfolio',
        label: '📊 Portfolio',
        icon: PieChart,
        description: 'Multi-symbol overview - all symbols at a glance',
        group: 'Grid Bot',
      },
      {
        id: 'positions',
        label: 'Positions',
        icon: Layers3,
        badge: openPositions ?? undefined,
        description: 'Active grids & execution state',
        group: 'Grid Bot',
      },
      {
        id: 'config',
        label: 'Configuration',
        icon: SlidersHorizontal,
        description: 'Bot parameters and reconciliation tools',
        group: 'Grid Bot',
      },
      {
        id: 'risk',
        label: 'Risk & Safety',
        icon: ShieldCheck,
        description: 'Risk analytics and protection systems',
        group: 'Grid Bot',
      },
      // ── Options Trading ──────────────────────────────────────
      {
        id: 'options',
        label: '📈 Options',
        icon: CandlestickChart,
        description: 'Options trading - manage calls/puts positions',
        group: 'Options Trading',
      },
      {
        id: 'options_chain',
        label: '🔗 Options Chain',
        icon: Table2,
        description: 'Options chain - market data, IV, Greeks, strike selection',
        group: 'Options Trading',
      },
      {
        id: 'strategy_builder',
        label: '🏗️ Strategy Builder',
        icon: Workflow,
        description: 'Multi-leg options strategies - straddles, iron condors, spreads',
        group: 'Options Trading',
      },
      {
        id: 'mv_straddle',
        label: '📊 MV Straddle',
        icon: Scale,
        description: 'Market View Straddle - volatility-driven directional neutral strategy',
        group: 'Options Trading',
      },
      // ── Algorithms ───────────────────────────────────────────
      {
        id: 'mmm',
        label: '💰 MMM',
        icon: Coins,
        description: 'Money Mind & Method - BTC 0DTE options selling algorithm',
        group: 'Algorithms',
      },
      {
        id: 'ssr_algo',
        label: '🦋 SSR ALGO',
        icon: Zap,
        description: 'Modified Iron Butterfly - automated percentage-based strike selection',
        group: 'Algorithms',
      },
      {
        id: 'zero_dte',
        label: '⏱️ 0DTE Trading',
        icon: Timer,
        description: '0DTE options - autonomous strangle with premium balancing',
        group: 'Algorithms',
      },
      // ── Signals & ML ─────────────────────────────────────────
      {
        id: 'tradingview',
        label: '📊 TradingView',
        icon: RadioTower,
        description: 'TradingView webhook signals - buy/sell alerts from Pine Script',
        group: 'Signals & ML',
      },
      {
        id: 'rsi',
        label: 'RSI',
        icon: BarChart3,
        description: 'RSI safety monitor - mode-specific thresholds with hysteresis',
        group: 'Signals & ML',
      },
      {
        id: 'ml_trading',
        label: 'ML',
        icon: Brain,
        description:
          'Machine Learning trading insights, style analysis, and autonomous decision engine',
        group: 'Signals & ML',
      },
      // ── System ───────────────────────────────────────────────
      {
        id: 'botmanagement',
        label: 'Bot Management',
        icon: Terminal,
        description: 'tmux control, process management, and emergency controls',
        group: 'System',
      },
      {
        id: 'system_health',
        label: 'System Health',
        icon: Activity,
        description: 'Real-time system monitoring - CPU, memory, disk, process health, alerts',
        group: 'System',
      },
      {
        id: 'intelligence',
        label: 'Intelligence',
        icon: BookOpen,
        description: 'AI insights, documentation, market intel',
        group: 'System',
      },
      {
        id: 'todos',
        label: 'Todo List',
        icon: ListChecks,
        description: 'Track improvements and ideas for the trading bot',
        group: 'System',
      },
      // Week 3: Guardian Dashboard (feature flag controlled)
      ...(guardianEnabled
        ? [
          {
            id: 'guardian',
            label: '🛡️ Guardian',
            icon: ShieldCheck,
            description: 'WebUI robustness monitor - circuit breakers, metrics, health',
            group: 'System',
          },
        ]
        : []),
      // ── Labs ─────────────────────────────────────────────────
      {
        id: 'experimental',
        label: '🧪 Experimental',
        icon: Code,
        description: 'Experimental features - Auto-Delta Hedging, Kelly Criterion, research tools',
        group: 'Labs',
      },
      {
        id: 'advanced_features',
        label: '🚀 Advanced',
        icon: Database,
        description: 'Advanced data collection - Delta Exchange OHLCV, live streaming, technical indicators',
        group: 'Labs',
      },
    ],
    [openPositions, pendingOrders]
  );

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

  // Smart preload: only preload adjacent sections for instant switches
  // This replaces the old approach that loaded ALL 40+ components at once
  useEffect(() => {
    const preloadTimer = setTimeout(() => {
      preloadAdjacentSections(activeSection, sections);
    }, 2000); // Start preloading adjacent tabs 2s after render
    return () => clearTimeout(preloadTimer);
  }, [activeSection, sections]);

  const socket = connectionManagerRef.current?.socket;

  const renderInactivePanel = (title, message, cta = null) => (
    <div className="flex min-h-[200px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-700/70 bg-slate-900/40 p-6 text-center">
      <PauseCircle className="mb-3 h-10 w-10 text-slate-500" />
      <p className="text-sm font-semibold text-slate-200">{title}</p>
      <p className="mt-2 max-w-sm text-xs text-slate-400">{message}</p>
      {cta}
    </div>
  );

  const handleDeepLink = useCallback(
    (tab) => {
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
        positions: 'positions',
      };
      const sectionId = map[tab];
      if (sectionId) {
        setActiveSection(sectionId);
        showNotification(`Navigated to ${sectionId.replace('_', ' ')}`, 'info');
      }
    },
    [showNotification]
  );
  // Navigation handler that clears params when navigating via sidebar
  const handleSectionSelect = useCallback((sectionId) => {
    // Use startTransition for non-blocking navigation
    startTransition(() => {
      setActiveSection(sectionId);
      // Clear nav params when navigating via normal sidebar click
      setNavParams(null);
    });
  }, []);

  const renderTodos = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="list" />}>
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
    </Suspense>
  ), []);

  const renderSystemHealth = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="monitoring" />}>
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
    </Suspense>
  ), []);

  const renderZeroDTE = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="dashboard" />}>
      <div className="grid gap-6">
        <EnhancedErrorBoundary componentName="ZeroDTEDashboard">
          <ZeroDTEDashboard />
        </EnhancedErrorBoundary>
      </div>
    </Suspense>
  ), []);

  const renderExperimental = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="dashboard" />}>
      <div className="grid gap-6">
        <EnhancedErrorBoundary componentName="ExperimentalPanel">
          <ExperimentalPanel />
        </EnhancedErrorBoundary>
      </div>
    </Suspense>
  ), []);

  const renderAdvancedFeatures = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="dashboard" />}>
      <div className="grid gap-6">
        <EnhancedErrorBoundary componentName="AdvancedFeaturesPanel">
          <AdvancedFeaturesPanel />
        </EnhancedErrorBoundary>
      </div>
    </Suspense>
  ), []);

  const renderDashboard = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="dashboard" />}>
      <div className="grid gap-6">{/* Bot Monitoring Dashboard - Top Priority */}
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
    </Suspense>
  ), [socket, latencyStats, connectionQuality, botIsRunning, isMobile, botStatus, config]);

  const renderPositions = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="table" />}>
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
    </Suspense>
  ), [botIsRunning, isMobile]);

  // Options Trading Panel (Jan 2026)
  const renderOptions = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="table" />}>
      <div className="grid gap-4">
        <CollapsibleCard
          id="options-panel"
          title="📈 Options Trading"
          subtitle="Manage positions - Close/add existing"
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
    </Suspense>
  ), []);

  // Options Chain Panel (Jan 2026) - Market Data Viewer
  const renderOptionsChain = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="table" />}>
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
              <OptionsChainPanel buildYourOwnMode={navParams?.buildYourOwnMode || false} />
            </EnhancedErrorBoundary>
          </Suspense>
        </CollapsibleCard>
      </div>
    </Suspense>
  ), [navParams]);

  // Options Strategy Builder (Jan 2026) - Multi-leg strategy builder
  const renderStrategyBuilder = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="dashboard" />}>
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
    </Suspense>
  ), []);

  const renderRSI = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="monitoring" />}>
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
    </Suspense>
  ), [isMobile]);

  const renderRisk = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="monitoring" />}>
      <div className="grid gap-6">{/* Modern Unified Risk & Safety Dashboard */}
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
    </Suspense>
  ), [isMobile]);

  const renderConfig = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="default" />}>
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
    </Suspense>
  ), [config, configMeta, busy, loading, isMobile, featureFlags, handleConfigUpdate, handleClearCache]);

  const renderEmergency = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="default" />}>
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
    </Suspense>
  ), [isMobile, socket]);

  const renderMonitoring = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="monitoring" />}>
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
    </Suspense>
  ), [isMobile, botIsRunning, botStatus, config]);

  const renderIntelligence = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="default" />}>
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
    </Suspense>
  ), [isMobile, botIsRunning]);

  const renderMLTrading = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="dashboard" />}>
      <div className="grid gap-6">{/* ML Trading Insights */}
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
    </Suspense>
  ), [isMobile]);

  const renderBotManagement = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="monitoring" />}>
      <div className="grid gap-6">{/* PM2 Process Manager */}
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
                <LogsPanel />
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
    </Suspense>
  ), [isMobile, botIsRunning, logs]);

  // Memoize previously inline sections to prevent recreation on every render
  const renderPortfolio = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="list" />}>
      <SymbolPortfolio />
    </Suspense>
  ), []);

  const renderMVStraddle = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="default" />}>
      <MVStraddlePanel />
    </Suspense>
  ), []);

  const renderMMM = useMemo(() => (
    <MMMErrorBoundary>
      <MMMProvider socket={socket}>
        <Suspense fallback={<PanelSkeleton type="default" />}>
          <MMMDashboard />
        </Suspense>
      </MMMProvider>
    </MMMErrorBoundary>
  ), [socket]);

  const renderSSRAlgo = useMemo(() => (
    <SSRAlgoErrorBoundary>
      <Suspense fallback={<PanelSkeleton type="default" />}>
        <SSRAlgoDashboard />
      </Suspense>
    </SSRAlgoErrorBoundary>
  ), []);

  const renderTradingView = useMemo(() => (
    <Suspense fallback={<PanelSkeleton type="default" />}>
      <TradingViewSignals />
    </Suspense>
  ), []);

  const renderGuardian = useMemo(() => (
    guardianEnabled ? (
      <Suspense fallback={<PanelSkeleton type="monitoring" />}>
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
      </Suspense>
    ) : null
  ), [guardianEnabled]);

  // Section content lookup — only the active section's JSX is used
  // All values are memoized references, so no JSX is recreated on re-render
  const getSectionContent = useCallback((sectionId) => {
    const contentMap = {
      todos: renderTodos,
      system_health: renderSystemHealth,
      dashboard: renderDashboard,
      portfolio: renderPortfolio,
      positions: renderPositions,
      options: renderOptions,
      options_chain: renderOptionsChain,
      strategy_builder: renderStrategyBuilder,
      mv_straddle: renderMVStraddle,
      mmm: renderMMM,
      ssr_algo: renderSSRAlgo,
      risk: renderRisk,
      tradingview: renderTradingView,
      rsi: renderRSI,
      config: renderConfig,
      ml_trading: renderMLTrading,
      botmanagement: renderBotManagement,
      emergency: renderEmergency,
      intelligence: renderIntelligence,
      guardian: renderGuardian,
      zero_dte: renderZeroDTE,
      experimental: renderExperimental,
      advanced_features: renderAdvancedFeatures,
    };
    return contentMap[sectionId] || renderDashboard;
  }, [
    renderTodos, renderSystemHealth, renderDashboard, renderPortfolio,
    renderPositions, renderOptions, renderOptionsChain, renderStrategyBuilder,
    renderMVStraddle, renderMMM, renderSSRAlgo, renderRisk, renderTradingView,
    renderRSI, renderConfig, renderMLTrading, renderBotManagement,
    renderEmergency, renderIntelligence, renderGuardian, renderZeroDTE,
    renderExperimental, renderAdvancedFeatures,
  ]);

  const activeContent = getSectionContent(activeSection);

  // Show backend down error page if backend is not responding
  if (backendDown) {
    return <BackendDownError onRetry={fetchInitialData} />;
  }

  return (
    <InstanceProvider>
      <SymbolProvider>
        <AutoloopProvider>
          <MobileOptimizationProvider>
            <div className="relative min-h-screen bg-surface text-slate-100">
              {/* V6.0: Instance Context Bar - REMOVED: Confusing, instance selection should be in BotManagement only */}
              {/* <InstanceContextBar 
            status={{ running: botIsRunning }}
            pnl={{ total: totalPnl }}
          /> */}
              {/* Autoloop Status Bar - Shows running background autoloops */}
              <AutoloopStatusBar />
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
                  lastUpdated,
                }}
                processStatus={{
                  guardianPid: botStatus?.guardian_health?.pid || null,
                  tradingBotPid: botStatus?.pid || null,
                  healthBotPid: botStatus?.heartbeat?.pid || null,
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

              <main
                className="pt-60 lg:pt-56 pb-[calc(7rem+env(safe-area-inset-bottom))]"
                style={{ marginTop: 'calc(env(safe-area-inset-top) + 8px)' }}
              >
                <MobileNav
                  sections={sections}
                  activeSection={activeSection}
                  onSelect={handleSectionSelect}
                />
                <div className="w-full">
                  <div key={activeSection} className="animate-fade-in" style={{ animationDuration: '150ms' }}>
                    {activeContent}
                  </div>
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
        </AutoloopProvider>
      </SymbolProvider>
    </InstanceProvider>
  );
}

export default App;
