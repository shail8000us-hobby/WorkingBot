import React from 'react';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import { OptionsPanel } from '../components/options';

const OptionsPage = React.memo(function OptionsPage() {
  return (
    <div className="grid gap-1">
      <CollapsibleCard
        id="options-panel"
        title="📈 Options Trading"
        subtitle="Manage positions - Close/add existing"
        accent="violet"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="OptionsPanel">
          <OptionsPanel />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );
});

export default OptionsPage;
