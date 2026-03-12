import React, { Suspense } from 'react';
import PanelSkeleton from '../components/common/PanelSkeleton';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';

const LoadingFallback = ({ message }) => (
  <div className="flex items-center justify-center gap-3 p-8 text-slate-400">
    <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-600 border-t-blue-400" />
    <span className="text-sm">{message}</span>
  </div>
);

const PM2Panel = React.lazy(() => import('../components/PM2Panel'));
const BotManagementDashboard = React.lazy(
  () => import('../components/BotManagement/BotManagementDashboard')
);
const LogsPanel = React.lazy(() => import('../components/LogsPanel'));

const BotManagementPage = React.memo(function BotManagementPage({ isMobile }) {
  return (
    <Suspense fallback={<PanelSkeleton type="monitoring" />}>
      <div className="grid gap-2">
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
          <Suspense fallback={<LoadingFallback message="Streaming logs..." />}>
            <EnhancedErrorBoundary componentName="LogsPanel">
              <LogsPanel />
            </EnhancedErrorBoundary>
          </Suspense>
        </CollapsibleCard>
      </div>
    </Suspense>
  );
});

export default BotManagementPage;
