'use client';

import { BotActionsPanel } from '@/components/actions/BotActionsPanel';

export default function ActionsPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Bot Actions</h1>
          <p className="text-muted-foreground mt-2">
            Real-time bot decisions and future intentions
          </p>
        </div>
        <BotActionsPanel />
      </div>
    </div>
  );
}

