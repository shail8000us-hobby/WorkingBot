import React from 'react';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import { OptionsPanel } from '../components/options';
import AutoHedgeConfigCard from '../components/options/AutoHedgeConfigCard';

const OptionsPage = React.memo(function OptionsPage() {
  return (
    <div className="grid gap-1">
      <EnhancedErrorBoundary componentName="OptionsPanel">
        <OptionsPanel />
      </EnhancedErrorBoundary>

      <CollapsibleCard
        id="auto-hedge-config"
        title="⚡ Auto Delta Hedge"
        subtitle="Automatically hedge delta when threshold is breached"
        accent="amber"
        defaultOpen={false}
      >
        <EnhancedErrorBoundary componentName="AutoHedgeConfigCard">
          <AutoHedgeConfigCard />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );
});

export default OptionsPage;
