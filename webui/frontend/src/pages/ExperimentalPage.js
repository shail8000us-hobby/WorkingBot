import React from 'react';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import ExperimentalPanel from '../components/ExperimentalPanel';

const ExperimentalPage = React.memo(function ExperimentalPage() {
  return (
    <div className="grid gap-2">
      <EnhancedErrorBoundary componentName="ExperimentalPanel">
        <ExperimentalPanel />
      </EnhancedErrorBoundary>
    </div>
  );
});

export default ExperimentalPage;
