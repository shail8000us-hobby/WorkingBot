'use client';

import { RSIPanel } from '@/components/rsi/RSIPanel';

export default function RSIPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">RSI Safety Monitor</h1>
          <p className="text-muted-foreground mt-2">
            Mode-specific RSI thresholds with hysteresis protection
          </p>
        </div>
        <RSIPanel />
      </div>
    </div>
  );
}

