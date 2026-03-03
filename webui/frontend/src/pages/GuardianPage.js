import React from 'react';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import GuardianDashboard from '../components/GuardianDashboard';

const GuardianPage = React.memo(function GuardianPage({ guardianEnabled }) {
  if (!guardianEnabled) return null;

  return (
    <div className="grid gap-2">
      <CollapsibleCard
        id="guardian-dashboard"
        title="🛡️ Guardian Dashboard"
        subtitle="WebUI Robustness Monitor - Circuit breakers, metrics, and health"
        accent="emerald"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="GuardianDashboard">
          <GuardianDashboard />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );
});

export default GuardianPage;
