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

const ConfigPanel = React.lazy(() => import('../components/ConfigPanel'));
const SyncReconciliationPanel = React.lazy(() => import('../components/SyncReconciliationPanel'));
const ReconciliationPanelV2 = React.lazy(() => import('../components/ReconciliationPanelV2'));

const ConfigPage = React.memo(function ConfigPage({
  config,
  configMeta,
  busy,
  loading,
  isMobile,
  featureFlags,
  handleConfigUpdate,
  handleClearCache,
}) {
  return (
    <Suspense fallback={<PanelSkeleton type="default" />}>
      <div className="grid gap-2">
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
  );
});

export default ConfigPage;
