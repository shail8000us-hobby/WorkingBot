'use client';

import { StrategyComparisonPanel } from '@/components/strategy/StrategyComparisonPanel';

export default function StrategyEditorPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Strategy Editor</h1>
          <p className="text-muted-foreground mt-2">
            Visual strategy builder with templates, forms, comparison, and backtest capabilities
          </p>
        </div>
        <StrategyComparisonPanel />
      </div>
    </div>
  );
}

