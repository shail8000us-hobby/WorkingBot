import React from 'react';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import { OptionsChainPanel } from '../components/optionsChain';

const OptionsChainPage = React.memo(function OptionsChainPage({ navParams }) {
  return (
    <div className="grid gap-2">
      <CollapsibleCard
        id="options-chain-panel"
        title="🔗 Options Chain"
        subtitle="Live options chain - IV, Greeks, strike selection by expiry"
        accent="cyan"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="OptionsChainPanel">
          <OptionsChainPanel buildYourOwnMode={navParams?.buildYourOwnMode || false} />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );
});

export default OptionsChainPage;
