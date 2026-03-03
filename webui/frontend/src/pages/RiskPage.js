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

const RiskSafetyDashboard = React.lazy(() => import('../components/RiskSafetyDashboard'));
const CapitalProtectionPanel = React.lazy(() => import('../components/CapitalProtectionPanel'));
const LiquidationProtectionPanel = React.lazy(() => import('../components/LiquidationProtectionPanel'));
const ErrorIntelligencePanel = React.lazy(() => import('../components/ErrorIntelligencePanel_simple'));
const ErrorIntelligenceLive = React.lazy(() => import('../components/ErrorIntelligenceLive'));
const RobustnessPanel = React.lazy(() => import('../components/RobustnessPanel'));
const GuardianPanel = React.lazy(() => import('../components/GuardianPanel'));

const RiskPage = React.memo(function RiskPage({ isMobile, botIsRunning }) {
  return (
    <Suspense fallback={<PanelSkeleton type="monitoring" />}>
      <div className="grid gap-2">
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
            <InactivePanel
              title="Error intelligence idle"
              message="Live anomaly scanning requires real-time logs from the trading engine and guardian. Start the bot to resume stream analysis."
            />
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
  );
});

export default RiskPage;
