import React from 'react';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import RSIPanel from '../components/RSIPanel';

const RSIPage = React.memo(function RSIPage({ isMobile }) {
  return (
    <div className="grid gap-2">
      <CollapsibleCard
        id="rsi-panel"
        title="📊 RSI Safety Monitor (Layer 6)"
        subtitle="Mode-specific RSI thresholds with hysteresis protection"
        accent="purple"
        defaultOpen={!isMobile}
      >
        <EnhancedErrorBoundary componentName="RSIPanel">
          <RSIPanel />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );
});

export default RSIPage;
