import React from 'react';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import ZeroDTEDashboard from '../components/zero_dte/ZeroDTEDashboard';

const ZeroDTEPage = React.memo(function ZeroDTEPage() {
  return (
    <div className="grid gap-2">
      <EnhancedErrorBoundary componentName="ZeroDTEDashboard">
        <ZeroDTEDashboard />
      </EnhancedErrorBoundary>
    </div>
  );
});

export default ZeroDTEPage;
