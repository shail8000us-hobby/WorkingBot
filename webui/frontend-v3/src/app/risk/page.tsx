'use client';

import { RiskLimitsPanel } from '@/components/risk/RiskLimitsPanel';
import { RiskMetricsPanel } from '@/components/risk/RiskMetricsPanel';

export default function RiskPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Risk & Safety</h1>
          <p className="text-muted-foreground mt-2">
            Risk analytics and protection systems
          </p>
        </div>
        <div className="grid gap-6">
          <RiskMetricsPanel />
          <RiskLimitsPanel />
        </div>
      </div>
    </div>
  );
}

