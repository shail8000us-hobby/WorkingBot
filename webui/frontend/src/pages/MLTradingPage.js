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

const MLInsightsPanel = React.lazy(() => import('../components/options/MLInsightsPanel'));
const MLStyleProfile = React.lazy(() => import('../components/options/MLStyleProfile'));
const MLOpportunityScanner = React.lazy(() => import('../components/options/MLOpportunityScanner'));
const MLDecisionCenter = React.lazy(() => import('../components/options/MLDecisionCenter'));
const MLModelMonitor = React.lazy(() => import('../components/options/MLModelMonitor'));
const DeltaTradeSync = React.lazy(() => import('../components/options/DeltaTradeSync'));

const MLTradingPage = React.memo(function MLTradingPage({ isMobile }) {
  return (
    <Suspense fallback={<PanelSkeleton type="dashboard" />}>
      <div className="grid gap-2">
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
    </Suspense>
  );
});

export default MLTradingPage;
