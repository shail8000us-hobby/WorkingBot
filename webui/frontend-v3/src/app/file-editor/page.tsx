'use client';

import { FileEditor } from '@/components/file-editor';

export default function FileEditorPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">File Editor</h1>
          <p className="text-muted-foreground mt-2">
            Edit code files with file browser, syntax highlighting, and save functionality
          </p>
        </div>
        <FileEditor />
      </div>
    </div>
  );
}

