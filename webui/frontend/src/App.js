import React, { useState, useEffect, useMemo, useCallback, Suspense, startTransition } from 'react';
import { useLocation, useNavigate, Routes, Route, Navigate } from 'react-router-dom';
import { Alert, Snackbar } from '@mui/material';
// framer-motion AnimatePresence removed: replaced with CSS for instant panel switches

// Week 2: Zustand store and data aggregator integration
import { dataAggregator } from './services/dataAggregator';

import TopBar from './components/layout/TopBar';
import Sidebar from './components/layout/Sidebar';
import { userPreferences } from './utils/storage.ts';
import { perfMonitor } from './utils/performanceMonitor';
import { useThemeMode } from './hooks/useThemeMode';
import { useSystemStatus } from './context/SystemStatusContext';
import { useBotControl } from './hooks/useBotControl';
import { useIsMobile } from './hooks/useIsMobile';
import { useLatencyTracker } from './hooks/useLatencyTracker';
import { useConnectionActions } from './hooks/useConnectionActions';
import { useAppEventListeners } from './hooks/useAppEventListeners';

// Phase 2: UI/UX Modernization - Import new styles
import './styles/animations.css';
import './styles/typography.css';
import './styles/micro-interactions.css';
import { useSocketConnection } from './hooks/useSocketConnection';
import { useConfigManager } from './hooks/useConfigManager';
import { useTradingData } from './hooks/useTradingData';
import MMMErrorBoundary from './components/mmm/MMMErrorBoundary';
import { MMMProvider } from './components/mmm/MMMContext';
import { AutoloopProvider } from './context/AutoloopContext';
import AutoloopStatusBar from './components/positionAdjustment/AutoloopStatusBar';
import IdleIndicator from './components/IdleIndicator';
import SafetyWarningBanner from './components/SafetyWarningBanner';
import OfflineIndicator from './components/OfflineIndicator';
// BackendDownError must NOT be lazy-loaded — it's the error fallback for backend failures
// and must be available immediately (lazy components need Suspense which may not be ready)
import BackendDownError from './components/BackendDownError';
import SymbolContextBar from './components/layout/SymbolContextBar';
import ConnectionStatusBar from './components/layout/ConnectionStatusBar';
import BatteryIndicator from './components/BatteryIndicator';
// Mobile indicators removed for cleaner UI
// import MobileBatteryIndicator from './components/MobileBatteryIndicator';
// import TailscaleMobileOptimizer from './components/TailscaleMobileOptimizer';
import './App.css';

// Phase 2.3: Extracted navigation config, preloader, and MobileNav
import { buildSections } from './config/navigationSections';
import { prefetchAllPages } from './utils/pagePrefetch';
import MobileNav from './components/layout/MobileNav';

// Phase 12: Route-level lazy loading — each page is its own chunk, only downloaded when visited
const TodosPage = React.lazy(() => import('./pages/TodosPage'));
const OptionsPage = React.lazy(() => import('./pages/OptionsPage'));
const SSRAlgoPage = React.lazy(() => import('./pages/SSRAlgoPage'));
const TradingViewPage = React.lazy(() => import('./pages/TradingViewPage'));
const ZeroDTEPage = React.lazy(() => import('./pages/ZeroDTEPage'));
const ExperimentalPage = React.lazy(() => import('./pages/ExperimentalPage'));
const AdvancedFeaturesPage = React.lazy(() => import('./pages/AdvancedFeaturesPage'));
const MVStraddlePage = React.lazy(() => import('./pages/MVStraddlePage'));
const RSIPage = React.lazy(() => import('./pages/RSIPage'));
const RiskPage = React.lazy(() => import('./pages/RiskPage'));
const IntelligencePage = React.lazy(() => import('./pages/IntelligencePage'));
const OptionsChainPage = React.lazy(() => import('./pages/OptionsChainPage'));
const StrategyBuilderPage = React.lazy(() => import('./pages/StrategyBuilderPage'));
const MMMPage = React.lazy(() => import('./pages/MMMPage'));
const MMMXPage = React.lazy(() => import('./pages/MMMXPage'));
const ICPage = React.lazy(() => import('./pages/ICPage'));
const SSDHPage = React.lazy(() => import('./pages/SSDHPage'));
const PortfolioMarginPage = React.lazy(() => import('./pages/PortfolioMarginPage'));
const MLTradingPage = React.lazy(() => import('./pages/MLTradingPage'));
const BotManagementPage = React.lazy(() => import('./pages/BotManagementPage'));
const EmergencyPage = React.lazy(() => import('./pages/EmergencyPage'));
const MonitoringPage = React.lazy(() => import('./pages/MonitoringPage'));
const ConfigPage = React.lazy(() => import('./pages/ConfigPage'));
const DashboardPage = React.lazy(() => import('./pages/DashboardPage'));
const PatiencePage = React.lazy(() => import('./pages/PatiencePage'));
const OIPage = React.lazy(() => import('./pages/OIPage'));

// Lazy components still used directly in App.js
const FloatingPriceWidget = React.lazy(() => import('./components/FloatingPriceWidget'));

// Mobile pages
const MobileDashboard = React.lazy(() => import('./mobile/MobileDashboard'));
const MobileControl = React.lazy(() => import('./mobile/MobileControl'));
const MobileSettingsNav = React.lazy(() => import('./mobile/MobileSettingsNav'));
const MobileConfig = React.lazy(() => import('./mobile/MobileConfig'));
const MobileRisk = React.lazy(() => import('./mobile/MobileRisk'));
const MobileMonitoring = React.lazy(() => import('./mobile/MobileMonitoring'));


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
  const [featureFlags, setFeatureFlags] = useState({
    reconciliation_v2: false,
    reconciliation_v2_dry_run: true,
  });
  // Phase 12: Route-based navigation — activeSection derived from URL
  const location = useLocation();
  const navigate = useNavigate();
  const activeSection = useMemo(() => {
    const path = location.pathname.replace(/^\//, '');
    return path || userPreferences.selectedSection || 'options';
  }, [location.pathname]);
  const navParams = location.state; // Navigation params via router state
  const [lastUpdated, setLastUpdated] = useState(null);
  const [logs, setLogs] = useState([]);

  // Phase 2.4: Extracted hooks
  const isMobile = useIsMobile();
  const { latencyStats, pushLatencySample } = useLatencyTracker();

  // Custom hooks for business logic
  const {
    tradingSnapshot,
    setTradingSnapshot,
    botStatus,
    setBotStatus,
    botIsRunning,
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

  const showNotification = useCallback((message, severity = 'info') => {
    setNotification({ open: true, message, severity });
  }, []);

  const handleCloseNotification = useCallback(() => {
    setNotification((prev) => ({ ...prev, open: false }));
  }, []);

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
    setLogs,
    setConnectionState,
    setConnectionQuality,
    setLastUpdated,
    showNotification: (message, severity) => setNotification({ open: true, message, severity }),
    pushLatencySample,
    debouncedFetchInitialData,
  });

  // Phase 2.4: Connection actions extracted to hooks/useConnectionActions.js
  const { ensureFresh, handleHardRefresh, handleClearCache } = useConnectionActions(
    connectionManagerRef,
    showNotification
  );

  // Phase 2.4: Global event listeners extracted to hooks/useAppEventListeners.js
  useAppEventListeners({ ensureFresh, handleStartBot, handleStopBot, showNotification });

  // Initial data load - only run once on mount
  useEffect(() => {
    fetchInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty deps = run only once on mount

  // Phase 2.3: Navigation sections extracted to config/navigationSections.js
  const sections = useMemo(
    () => buildSections({ pendingOrders }),
    [pendingOrders]
  );

  useEffect(() => {
    const handleKeyboardNav = (event) => {
      const index = event.detail;
      if (typeof index === 'number' && sections[index]) {
        navigate('/' + sections[index].id);
      }
    };
    window.addEventListener('keyboard-tab-change', handleKeyboardNav);
    return () => window.removeEventListener('keyboard-tab-change', handleKeyboardNav);
  }, [sections, navigate]);

  useEffect(() => {
    if (!sections.some((section) => section.id === activeSection) && sections.length > 0) {
      navigate('/' + sections[0].id, { replace: true });
    }
  }, [sections, activeSection, navigate]);

  // Aggressive preload: after 5s idle, preload ALL page chunks in background
  // This makes every subsequent tab switch instant (no Suspense flash)
  useEffect(() => {
    const preloadTimer = setTimeout(() => {
      prefetchAllPages();
    }, 5000);
    return () => clearTimeout(preloadTimer);
  }, []); // Only once on mount

  const socket = connectionManagerRef.current?.socket;

  // Navigation handler — sidebar clicks navigate via router
  const handleSectionSelect = useCallback((sectionId) => {
    navigate('/' + sectionId);
  }, [navigate]);

  // Navigation with params — used by Strategy Builder to pass buildYourOwnMode etc.
  const handleNavigateToTab = useCallback((tabId, params) => {
    navigate('/' + tabId, { state: params || null });
  }, [navigate]);


  // Phase 12: Route-based rendering removed inline switch — see <Routes> in JSX below

  // Show backend down error page if backend is not responding
  if (backendDown) {
    return <BackendDownError onRetry={fetchInitialData} />;
  }

  return (
    <AutoloopProvider>
      <div className="relative min-h-screen bg-surface text-slate-100">
        {/* Autoloop Status Bar */}
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

        {/* Phase 2: Symbol Context Bar - Always visible below TopBar on desktop, hidden on mobile */}
        {!isMobile && (
          <SymbolContextBar
            gridInfo={config?.grid}
            status={{ running: botIsRunning }}
            pnl={totalPnl ? { total: totalPnl } : null}
            botStatus={botStatus}
          />
        )}

        <Sidebar
          sections={sections}
          activeSection={activeSection}
          onSelect={handleSectionSelect}
        />

        <main
          className={`relative z-0 pt-12 lg:pt-56 ${isMobile ? 'pb-16' : 'pb-[calc(7rem+env(safe-area-inset-bottom))]'}`}
          style={{ marginTop: 'calc(env(safe-area-inset-top) + 8px)' }}
        >
          <div className="w-full">
            <div className="animate-fade-in" style={{ animationDuration: '150ms' }}>
              <Suspense fallback={<div className="flex items-center justify-center p-12 text-slate-500">Loading...</div>}>
                <Routes>
                  <Route path="/" element={<Navigate to={`/${userPreferences.selectedSection || 'dashboard'}`} replace />} />
                  <Route path="/todos" element={<TodosPage />} />
                  <Route path="/dashboard" element={isMobile ? <MMMErrorBoundary><MMMProvider socket={socket}><MobileDashboard socket={socket} /></MMMProvider></MMMErrorBoundary> : <DashboardPage socket={socket} latencyStats={latencyStats} connectionQuality={connectionQuality} botIsRunning={botIsRunning} isMobile={isMobile} botStatus={botStatus} config={config} />} />
                  <Route path="/options" element={<OptionsPage />} />
                  <Route path="/options_chain" element={<OptionsChainPage navParams={navParams} />} />
                  <Route path="/strategy_builder" element={<StrategyBuilderPage onNavigateToTab={handleNavigateToTab} />} />
                  <Route path="/mv_straddle" element={<MVStraddlePage />} />
                  <Route path="/mmm" element={isMobile ? <MMMErrorBoundary><MMMProvider socket={socket}><MobileDashboard socket={socket} /></MMMProvider></MMMErrorBoundary> : <MMMPage socket={socket} />} />
                  <Route path="/mmmx" element={<MMMXPage socket={socket} />} />
                  <Route path="/ic" element={<ICPage socket={socket} />} />
                  <Route path="/ssr_algo" element={<SSRAlgoPage />} />
                  <Route path="/ssdh" element={<SSDHPage />} />
                  <Route path="/risk" element={<RiskPage isMobile={isMobile} botIsRunning={botIsRunning} />} />
                  <Route path="/tradingview" element={<TradingViewPage />} />
                  <Route path="/rsi" element={<RSIPage isMobile={isMobile} />} />
                  <Route path="/config" element={<ConfigPage config={config} configMeta={configMeta} busy={busy} loading={loading} isMobile={isMobile} featureFlags={featureFlags} handleConfigUpdate={handleConfigUpdate} handleClearCache={handleClearCache} />} />
                  <Route path="/control" element={isMobile ? <MMMErrorBoundary><MMMProvider socket={socket}><MobileControl socket={socket} /></MMMProvider></MMMErrorBoundary> : <Navigate to="/dashboard" replace />} />
                  <Route path="/settings_mobile" element={isMobile ? <MobileSettingsNav /> : <Navigate to="/config" replace />} />
                  <Route path="/ml_trading" element={<MLTradingPage isMobile={isMobile} />} />
                  <Route path="/botmanagement" element={<BotManagementPage isMobile={isMobile} botIsRunning={botIsRunning} />} />
                  <Route path="/emergency" element={<EmergencyPage isMobile={isMobile} socket={socket} />} />
                  <Route path="/intelligence" element={<IntelligencePage isMobile={isMobile} botIsRunning={botIsRunning} />} />
                  <Route path="/zero_dte" element={<ZeroDTEPage />} />
                  <Route path="/portfolio_margin" element={<PortfolioMarginPage />} />
                  <Route path="/patience" element={<PatiencePage />} />
                  <Route path="/oi" element={<OIPage />} />
                  <Route path="/experimental" element={<ExperimentalPage />} />
                  <Route path="/advanced_features" element={<AdvancedFeaturesPage />} />
                  <Route path="/monitoring" element={<MonitoringPage isMobile={isMobile} botIsRunning={botIsRunning} botStatus={botStatus} config={config} />} />
                  <Route path="*" element={<Navigate to="/dashboard" replace />} />
                </Routes>
              </Suspense>
            </div>
          </div>
        </main>

        {/* Mobile Bottom Navigation - rendered outside main for proper fixed positioning */}
        {isMobile && (
          <MobileNav
            sections={sections}
            activeSection={activeSection}
            onSelect={handleSectionSelect}
          />
        )}

        <Snackbar
          open={notification.open}
          autoHideDuration={5000}
          onClose={handleCloseNotification}
          anchorOrigin={isMobile ? { vertical: 'top', horizontal: 'center' } : { vertical: 'bottom', horizontal: 'right' }}
          style={isMobile ? { marginTop: '80px' } : {}}
        >
          <Alert
            onClose={handleCloseNotification}
            severity={notification.severity}
            sx={{ width: '100%' }}
          >
            {notification.message}
          </Alert>
        </Snackbar>

        <div className="pointer-events-none fixed inset-x-0 top-16 z-10 hidden lg:flex justify-center lg:pl-64">
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

        {/* Mobile Status Indicators (Battery + Connection) */}
        {isMobile && (
          <>
            <BatteryIndicator />
            <ConnectionStatusBar connectionState={connectionState} connectionQuality={connectionQuality} />
          </>
        )}

        {/* Floating Price Widget - Real-time BTC/ETH prices (hidden on mobile) */}
        {!isMobile && (
          <Suspense fallback={null}>
            <FloatingPriceWidget />
          </Suspense>
        )}
      </div>
    </AutoloopProvider>
  );
}

export default App;
