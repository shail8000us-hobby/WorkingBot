'use client';

import PM2Panel from '@/components/process/PM2Panel';

export default function BotManagementPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Bot Management</h1>
          <p className="text-muted-foreground mt-2">
            Process management and bot control
          </p>
        </div>
        <PM2Panel />
      </div>
    </div>
  );
}

