'use client';

import { LogViewerPanel } from '@/components/logs/LogViewerPanel';

export default function LogsPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Logs</h1>
          <p className="text-muted-foreground mt-2">
            Live log streaming with filtering and export
          </p>
        </div>
        <LogViewerPanel />
      </div>
    </div>
  );
}

