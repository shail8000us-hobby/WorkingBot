'use client';

import { MonitoringDashboard } from '@/components/monitoring/MonitoringDashboard';
import { MonitoringRecoveryPanel } from '@/components/monitoring/MonitoringRecoveryPanel';

export default function MonitoringPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Monitoring</h1>
          <p className="text-muted-foreground mt-2">
            Real-time trading monitoring and analytics
          </p>
        </div>
              <MonitoringDashboard />
              <MonitoringRecoveryPanel />
      </div>
    </div>
  );
}

