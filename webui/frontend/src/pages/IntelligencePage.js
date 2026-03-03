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

const AIAdvisorWidget = React.lazy(() => import('../components/AIAdvisorWidget'));
const InstitutionalAIPanel = React.lazy(() => import('../components/InstitutionalAIPanel'));
const CommandKnowledgeBase = React.lazy(() => import('../components/CommandKnowledgeBase'));
const MarketNewsWidget = React.lazy(() => import('../components/MarketNewsWidget'));

const IntelligencePage = React.memo(function IntelligencePage({ isMobile, botIsRunning }) {
  return (
    <Suspense fallback={<PanelSkeleton type="default" />}>
      <div className="grid gap-2">
        <CollapsibleCard
          id="ai-insights"
          title="AI Advisor & Institutional Toolkit"
          subtitle="Continuous intelligence, incident analysis, and strategic guidance"
          accent="violet"
          defaultOpen={!isMobile}
        >
          {botIsRunning ? (
            <div className="flex flex-col gap-6 w-full">
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
            <InactivePanel
              title="AI Advisor paused"
              message="AI-driven insights populate after the trading engine streams fresh telemetry and market states."
            />
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
  );
});

export default IntelligencePage;
