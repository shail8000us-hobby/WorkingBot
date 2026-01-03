'use client';

import { ModeSwitcherPanel } from '@/components/mode-switcher';

export default function ModeSwitcherPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Mode Switcher</h1>
          <p className="text-muted-foreground mt-2">
            Automatic LONG/SHORT switching based on price - hysteresis, manual override, switch history
          </p>
        </div>
        <ModeSwitcherPanel />
      </div>
    </div>
  );
}

