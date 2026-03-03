import React from 'react';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import { StrategyBuilder } from '../components/optionsStrategy';

const StrategyBuilderPage = React.memo(function StrategyBuilderPage({ onNavigateToTab }) {
  return (
    <div className="grid gap-2">
      <EnhancedErrorBoundary componentName="StrategyBuilder">
        <StrategyBuilder onNavigateToTab={onNavigateToTab} />
      </EnhancedErrorBoundary>
    </div>
  );
});

export default StrategyBuilderPage;
