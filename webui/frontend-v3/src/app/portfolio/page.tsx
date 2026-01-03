'use client';

import { SymbolPortfolio } from '@/components/portfolio';

export default function PortfolioPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Portfolio</h1>
          <p className="text-muted-foreground mt-2">
            Multi-symbol overview - all symbols at a glance
          </p>
        </div>
        <SymbolPortfolio />
      </div>
    </div>
  );
}

