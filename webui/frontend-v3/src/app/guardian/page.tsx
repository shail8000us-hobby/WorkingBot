'use client';

import { GuardianDashboard } from '@/components/guardian/GuardianDashboard';

export default function GuardianPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Guardian</h1>
          <p className="text-muted-foreground mt-2">
            Autonomous safety system monitoring and controls
          </p>
        </div>
        <GuardianDashboard />
      </div>
    </div>
  );
}
