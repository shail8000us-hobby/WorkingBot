'use client';

import ConfigEditorPanel from '@/components/config/ConfigEditorPanel';

export default function ConfigPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Configuration</h1>
          <p className="text-muted-foreground mt-2">
            Bot parameters and reconciliation tools
          </p>
        </div>
        <ConfigEditorPanel />
      </div>
    </div>
  );
}

