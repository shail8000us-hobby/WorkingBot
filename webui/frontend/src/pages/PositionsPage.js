import React from 'react';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import { PauseCircle } from 'lucide-react';
import PositionsPanel from '../components/PositionsPanel';

const InactivePanel = ({ title, message }) => (
  <div className="flex min-h-[200px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-700/70 bg-slate-900/40 p-6 text-center">
    <PauseCircle className="mb-3 h-10 w-10 text-slate-500" />
    <p className="text-sm font-semibold text-slate-200">{title}</p>
    <p className="mt-2 max-w-sm text-xs text-slate-400">{message}</p>
  </div>
);

const PositionsPage = React.memo(function PositionsPage({ botIsRunning, isMobile }) {
  return (
    <div className="grid gap-2">
      <CollapsibleCard
        id="positions-panel"
        title="Open Positions"
        subtitle="Real-time grid exposure and unrealized PnL"
        accent="emerald"
        defaultOpen={!isMobile}
      >
        {botIsRunning ? (
          <EnhancedErrorBoundary componentName="PositionsPanel">
            <PositionsPanel />
          </EnhancedErrorBoundary>
        ) : (
          <InactivePanel
            title="No positions until bot starts"
            message="Position inventory and tranche breakdown appear here after the trading engine is online."
          />
        )}
      </CollapsibleCard>
    </div>
  );
});

export default PositionsPage;
