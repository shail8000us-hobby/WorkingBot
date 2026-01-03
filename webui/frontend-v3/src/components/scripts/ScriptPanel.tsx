'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Code, Play, Pause, Trash2, FileCode } from 'lucide-react';

interface Script {
  id: string;
  name: string;
  description: string;
  language: 'python' | 'javascript';
  status: 'idle' | 'running' | 'completed' | 'error';
  last_run?: string;
  last_output?: string;
  created_at: string;
}

interface ScriptsResponse {
  data: {
    scripts: Script[];
    total: number;
    running: number;
  };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchScripts(): Promise<ScriptsResponse> {
  const response = await fetch('http://localhost:5555/api/scripts/list');
  if (!response.ok) {
    throw new Error('Failed to fetch scripts');
  }
  return response.json();
}

async function executeScript(id: string) {
  const response = await fetch(`http://localhost:5555/api/scripts/${id}/execute`, {
    method: 'POST',
  });
  return response.json();
}

export function ScriptPanel() {
  const [executing, setExecuting] = useState<string | null>(null);
  const [selectedScript, setSelectedScript] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['scripts'],
    queryFn: fetchScripts,
    refetchInterval: 5000,
  });

  const handleExecute = async (id: string) => {
    setExecuting(id);
    try {
      await executeScript(id);
      refetch();
    } catch (err) {
      console.error('Failed to execute script:', err);
    } finally {
      setExecuting(null);
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Code className="h-5 w-5" />
            Custom Scripts
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading scripts...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Custom Scripts</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load scripts'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const scripts = data?.data.scripts || [];
  const stats = data?.data;
  const selected = scripts.find((s) => s.id === selectedScript);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Code className="h-5 w-5" />
            Custom Scripts
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline">
              {stats?.running || 0} Running
            </Badge>
            <Button variant="outline" size="sm">
              <FileCode className="h-4 w-4 mr-2" />
              New Script
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Warning */}
        <Alert variant="destructive">
          <AlertDescription className="text-xs font-semibold">
            Custom scripts have full system access. Only run trusted code.
          </AlertDescription>
        </Alert>

        {/* Summary */}
        <div className="grid grid-cols-3 gap-4">
          <Card className="p-3">
            <p className="text-xs text-muted-foreground mb-1">Total Scripts</p>
            <p className="text-2xl font-bold">{stats?.total || 0}</p>
          </Card>
          <Card className="p-3">
            <p className="text-xs text-muted-foreground mb-1">Running</p>
            <p className="text-2xl font-bold text-green-600">{stats?.running || 0}</p>
          </Card>
          <Card className="p-3">
            <p className="text-xs text-muted-foreground mb-1">Idle</p>
            <p className="text-2xl font-bold text-gray-600">
              {(stats?.total || 0) - (stats?.running || 0)}
            </p>
          </Card>
        </div>

        {/* Scripts List */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <h3 className="text-sm font-semibold mb-2">Scripts</h3>
            {scripts.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Code className="h-12 w-12 mx-auto mb-3 opacity-20" />
                <p>No scripts available</p>
              </div>
            ) : (
              scripts.map((script) => (
                <Card
                  key={script.id}
                  className={`p-3 cursor-pointer transition-colors ${
                    selectedScript === script.id ? 'border-primary' : ''
                  }`}
                  onClick={() => setSelectedScript(script.id)}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <Code className="h-4 w-4 text-muted-foreground" />
                        <span className="font-semibold text-sm">{script.name}</span>
                      </div>
                      <p className="text-xs text-muted-foreground mb-2">
                        {script.description}
                      </p>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">
                          {script.language}
                        </Badge>
                        <Badge
                          variant={
                            script.status === 'running'
                              ? 'default'
                              : script.status === 'error'
                              ? 'destructive'
                              : 'secondary'
                          }
                          className="text-xs"
                        >
                          {script.status}
                        </Badge>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <Button
                      variant="default"
                      size="sm"
                      className="flex-1"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleExecute(script.id);
                      }}
                      disabled={executing === script.id || script.status === 'running'}
                    >
                      <Play className="h-3 w-3 mr-1" />
                      {executing === script.id ? 'Running...' : 'Run'}
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </Card>
              ))
            )}
          </div>

          {/* Output Panel */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold mb-2">Output</h3>
            {selected ? (
              <Card className="p-3">
                <div className="mb-2">
                  <h4 className="font-semibold text-sm mb-1">{selected.name}</h4>
                  {selected.last_run && (
                    <p className="text-xs text-muted-foreground">
                      Last run: {new Date(selected.last_run).toLocaleString()}
                    </p>
                  )}
                </div>
                <ScrollArea className="h-[300px] w-full rounded-md border bg-black p-3">
                  <pre className="text-xs font-mono text-green-400">
                    {selected.last_output || 'No output available'}
                  </pre>
                </ScrollArea>
              </Card>
            ) : (
              <Card className="p-8 text-center">
                <Code className="h-12 w-12 mx-auto mb-3 opacity-20" />
                <p className="text-sm text-muted-foreground">
                  Select a script to view output
                </p>
              </Card>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
