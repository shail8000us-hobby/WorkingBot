import React from 'react';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import AdvancedFeaturesPanel from '../components/AdvancedFeaturesPanel';

const AdvancedFeaturesPage = React.memo(function AdvancedFeaturesPage() {
  return (
    <div className="grid gap-2">
      <EnhancedErrorBoundary componentName="AdvancedFeaturesPanel">
        <AdvancedFeaturesPanel />
      </EnhancedErrorBoundary>
    </div>
  );
});

export default AdvancedFeaturesPage;
