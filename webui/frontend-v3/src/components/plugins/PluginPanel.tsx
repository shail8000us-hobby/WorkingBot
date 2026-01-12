'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Puzzle, Download, Trash2, Settings } from 'lucide-react';

interface Plugin {
  id: string;
  name: string;
  version: string;
  description: string;
  enabled: boolean;
  status: 'active' | 'inactive' | 'error';
  author: string;
  installed_at: string;
  category: string;
}

interface PluginsResponse {
  data: {
    plugins: Plugin[];
    total: number;
    enabled: number;
  };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchPlugins(): Promise<PluginsResponse> {
  const response = await fetch('http://localhost:5557/api/plugins/list');
  if (!response.ok) {
    throw new Error('Failed to fetch plugins');
  }
  return response.json();
}

async function togglePlugin(id: string, enabled: boolean) {
  const response = await fetch(`http://localhost:5557/api/plugins/${id}/toggle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
  return response.json();
}

export function PluginPanel() {
  const [toggling, setToggling] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['plugins'],
    queryFn: fetchPlugins,
    refetchInterval: 30000,
  });

  const handleToggle = async (id: string, enabled: boolean) => {
    setToggling(id);
    try {
      await togglePlugin(id, enabled);
      refetch();
    } catch (err) {
      console.error('Failed to toggle plugin:', err);
    } finally {
      setToggling(null);
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Puzzle className="h-5 w-5" />
            Plugin Management
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading plugins...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Plugin Management</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load plugins'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const plugins = data?.data.plugins || [];
  const stats = data?.data;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Puzzle className="h-5 w-5" />
            Plugin Management
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline">
              {stats?.enabled}/{stats?.total} Enabled
            </Badge>
            <Button variant="outline" size="sm">
              <Download className="h-4 w-4 mr-2" />
              Install
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Summary */}
        <div className="grid grid-cols-3 gap-4">
          <Card className="p-3">
            <p className="text-xs text-muted-foreground mb-1">Total Plugins</p>
            <p className="text-2xl font-bold">{stats?.total || 0}</p>
          </Card>
          <Card className="p-3">
            <p className="text-xs text-muted-foreground mb-1">Enabled</p>
            <p className="text-2xl font-bold text-green-600">{stats?.enabled || 0}</p>
          </Card>
          <Card className="p-3">
            <p className="text-xs text-muted-foreground mb-1">Disabled</p>
            <p className="text-2xl font-bold text-gray-600">
              {(stats?.total || 0) - (stats?.enabled || 0)}
            </p>
          </Card>
        </div>

        {/* Plugins List */}
        <div className="space-y-3">
          {plugins.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Puzzle className="h-12 w-12 mx-auto mb-3 opacity-20" />
              <p>No plugins installed</p>
              <Button variant="outline" size="sm" className="mt-4">
                <Download className="h-4 w-4 mr-2" />
                Browse Plugin Store
              </Button>
            </div>
          ) : (
            plugins.map((plugin) => (
              <Card key={plugin.id} className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <Puzzle className="h-4 w-4 text-muted-foreground" />
                      <h3 className="font-semibold">{plugin.name}</h3>
                      <Badge variant="outline" className="text-xs">
                        v{plugin.version}
                      </Badge>
                      <Badge variant="secondary" className="text-xs">
                        {plugin.category}
                      </Badge>
                      <Badge
                        variant={
                          plugin.status === 'active'
                            ? 'default'
                            : plugin.status === 'error'
                            ? 'destructive'
                            : 'secondary'
                        }
                        className="text-xs"
                      >
                        {plugin.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground mb-2">{plugin.description}</p>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span>By {plugin.author}</span>
                      <span>•</span>
                      <span>
                        Installed {new Date(plugin.installed_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <Switch
                      checked={plugin.enabled}
                      onCheckedChange={(checked) => handleToggle(plugin.id, checked)}
                      disabled={toggling === plugin.id}
                    />
                    <Button variant="ghost" size="sm">
                      <Settings className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              </Card>
            ))
          )}
        </div>

        {/* Available Plugins */}
        <div className="mt-6 p-4 border-t">
          <h3 className="text-sm font-semibold mb-3">Available Plugins</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="flex items-center gap-2">
              <Puzzle className="h-4 w-4 text-muted-foreground" />
              <span>Advanced Order Types</span>
            </div>
            <div className="flex items-center gap-2">
              <Puzzle className="h-4 w-4 text-muted-foreground" />
              <span>Custom Indicators</span>
            </div>
            <div className="flex items-center gap-2">
              <Puzzle className="h-4 w-4 text-muted-foreground" />
              <span>Risk Management Tools</span>
            </div>
            <div className="flex items-center gap-2">
              <Puzzle className="h-4 w-4 text-muted-foreground" />
              <span>Portfolio Analytics</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
