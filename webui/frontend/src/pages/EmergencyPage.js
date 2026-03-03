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

const EmergencyControlsPanel = React.lazy(() => import('../components/EmergencyControlsPanel'));
const ShutdownPanel = React.lazy(() => import('../components/ShutdownPanel'));

const EmergencyPage = React.memo(function EmergencyPage({ isMobile, socket }) {
  return (
    <Suspense fallback={<PanelSkeleton type="default" />}>
      <div className="grid gap-2">
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
  );
});

export default EmergencyPage;
