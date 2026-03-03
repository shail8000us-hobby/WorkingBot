import React from 'react';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import SystemHealthPanel from '../components/SystemHealthPanel';

const SystemHealthPage = React.memo(function SystemHealthPage() {
  return (
    <div className="grid gap-2">
      <CollapsibleCard
        id="system-health"
        title="📊 System Health Monitor"
        subtitle="Real-time system monitoring - CPU, memory, disk, process health, API status, alerts with auto-healing"
        accent="green"
        defaultOpen={true}
      >
        <EnhancedErrorBoundary componentName="SystemHealthPanel">
          <SystemHealthPanel />
        </EnhancedErrorBoundary>
      </CollapsibleCard>
    </div>
  );
});

export default SystemHealthPage;
