'use client';

import { PredictiveIntelligencePanel } from '@/components/intelligence/PredictiveIntelligencePanel';
import { AIAdvisorWidget } from '@/components/ai/AIAdvisorWidget';

export default function IntelligencePage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Intelligence</h1>
          <p className="text-muted-foreground mt-2">
            AI insights, documentation, and market intelligence
          </p>
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <PredictiveIntelligencePanel />
          <AIAdvisorWidget />
        </div>
      </div>
    </div>
  );
}

