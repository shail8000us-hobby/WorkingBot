import React, { Suspense } from 'react';
import PanelSkeleton from '../components/common/PanelSkeleton';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
import { VolatilityRegimePanel, UnrealizedPnLPanel } from '../components/panels';
import TradingModeSwitch from '../components/TradingModeSwitch';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import { PauseCircle } from 'lucide-react';

const LoadingFallback = ({ message }) => (
  <div className="flex items-center justify-center gap-3 p-8 text-slate-400">
    <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-600 border-t-blue-400" />
    <span className="text-sm">{message}</span>
  </div>
);

const InactivePanel = ({ title, message }) => (
  <div className="flex min-h-[200px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-700/70 bg-slate-900/40 p-6 text-center">
    <PauseCircle className="mb-3 h-10 w-10 text-slate-500" />
    <p className="text-sm font-semibold text-slate-200">{title}</p>
    <p className="mt-2 max-w-sm text-xs text-slate-400">{message}</p>
  </div>
);

const HealthCheckDashboard = React.lazy(() => import('../components/HealthCheckDashboard'));
const MonitoringDashboard = React.lazy(() => import('../components/MonitoringDashboard'));
const MarketSignalPanel = React.lazy(() => import('../components/MarketSignalPanel'));
const MonitoringPanel = React.lazy(() => import('../components/MonitoringPanel'));
const MonitoringRecoveryPanel = React.lazy(
  () => import('../components/panels/MonitoringRecoveryPanel')
);
const ProductionMonitoringDashboard = React.lazy(
  () => import('../components/ProductionMonitoringDashboard')
);

const DashboardPage = React.memo(function DashboardPage({
  socket,
  latencyStats,
  connectionQuality,
  botIsRunning,
  isMobile,
  botStatus,
  config,
}) {
  return (
    <Suspense fallback={<PanelSkeleton type="dashboard" />}>
      <div className="grid gap-2">
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
            <InactivePanel
              title="Market signal waiting for bot"
              message="Once the bot subscribes to exchange feeds we will display readiness scores and drift analytics."
            />
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
            <InactivePanel
              title="Monitoring idle"
              message="Process metrics and guardian heartbeat dashboards become available once services start."
            />
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
  );
});

export default DashboardPage;
