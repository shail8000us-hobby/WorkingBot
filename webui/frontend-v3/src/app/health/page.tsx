'use client';

import { SystemHealthPanel } from '@/components/health/SystemHealthPanel';

export default function HealthPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">System Health</h1>
          <p className="text-muted-foreground mt-2">
            Real-time system health monitoring and metrics
          </p>
        </div>
        <SystemHealthPanel />
      </div>
    </div>
  );
}
