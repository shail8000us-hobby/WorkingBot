import React, { Suspense } from 'react';
import PanelSkeleton from '../components/common/PanelSkeleton';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
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

const MonitoringPanel = React.lazy(() => import('../components/MonitoringPanel'));
const MonitoringRecoveryPanel = React.lazy(
  () => import('../components/panels/MonitoringRecoveryPanel')
);

const MonitoringPage = React.memo(function MonitoringPage({ isMobile, botIsRunning, botStatus, config }) {
  return (
    <Suspense fallback={<PanelSkeleton type="monitoring" />}>
      <div className="grid gap-2">
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
      </div>
    </Suspense>
  );
});

export default MonitoringPage;
