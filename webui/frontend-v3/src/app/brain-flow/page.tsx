'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Brain, AlertTriangle } from 'lucide-react';

export default function BrainFlowPage() {
  return (
    <div className="container mx-auto p-4 md:p-6">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Brain Flow Graph</h1>
          <p className="text-muted-foreground mt-2">
            Visual decision flowchart showing complete decision tree
          </p>
        </div>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5" />
              Bot Brain Decision Flow
            </CardTitle>
            <CardDescription>
              Visual flowchart showing complete decision tree
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                BotBrainAnalyzer component migration in progress. This feature will display the visual decision flowchart.
                See <code>/brain</code> page for current brain functionality.
              </AlertDescription>
            </Alert>
            <div className="mt-4 text-sm text-muted-foreground">
              <p>The Bot Brain Analyzer component needs to be migrated from v1 to v3.</p>
              <p className="mt-2">This will include:</p>
              <ul className="list-disc list-inside mt-2 space-y-1">
                <li>Decision Flow Graph visualization</li>
                <li>Action Sequences timeline</li>
                <li>Brain Modules list</li>
                <li>Real-time predictions</li>
              </ul>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

