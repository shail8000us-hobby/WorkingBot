'use client';

import { ConfigVisualEditor } from '@/components/config';
import { SlidersHorizontal } from 'lucide-react';

export default function ConfigVisualEditorPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <SlidersHorizontal className="h-8 w-8 text-purple-500" />
            Visual Config Editor
          </h1>
          <p className="text-muted-foreground mt-2">
            Edit configuration with forms or YAML - validation, diff preview, and auto-backup
          </p>
        </div>
        <ConfigVisualEditor />
      </div>
    </div>
  );
}

