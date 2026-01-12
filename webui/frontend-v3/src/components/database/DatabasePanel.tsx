'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Database, HardDrive } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

interface DatabaseStats {
  size_mb: number;
  tables: {
    name: string;
    rows: number;
    size_mb: number;
  }[];
  connections: {
    active: number;
    idle: number;
    total: number;
  };
  queries_per_second: number;
  avg_query_time_ms: number;
}

interface DatabaseResponse {
  data: DatabaseStats;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchDatabaseStats(): Promise<DatabaseResponse> {
  const response = await fetch('http://localhost:5557/api/database/stats');
  if (!response.ok) {
    throw new Error('Failed to fetch database stats');
  }
  return response.json();
}

export function DatabasePanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['database-stats'],
    queryFn: fetchDatabaseStats,
    refetchInterval: 10000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Database Statistics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading database statistics...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Database Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load database stats'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const stats = data?.data;
  if (!stats) return null;

  const totalRows = stats.tables.reduce((sum, table) => sum + table.rows, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="h-5 w-5" />
          Database Statistics
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Overview */}
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Database Size</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.size_mb.toFixed(1)} MB</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Total Rows</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalRows.toLocaleString()}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Queries/sec</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.queries_per_second.toFixed(1)}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Avg Query Time</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.avg_query_time_ms.toFixed(1)} ms</div>
            </CardContent>
          </Card>
        </div>

        {/* Connections */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold">Connection Pool</h3>
          <div className="grid grid-cols-3 gap-4">
            <Card className="p-3">
              <div className="text-center">
                <p className="text-xs text-muted-foreground mb-1">Active</p>
                <p className="text-2xl font-bold text-green-600">{stats.connections.active}</p>
              </div>
            </Card>
            <Card className="p-3">
              <div className="text-center">
                <p className="text-xs text-muted-foreground mb-1">Idle</p>
                <p className="text-2xl font-bold text-gray-600">{stats.connections.idle}</p>
              </div>
            </Card>
            <Card className="p-3">
              <div className="text-center">
                <p className="text-xs text-muted-foreground mb-1">Total</p>
                <p className="text-2xl font-bold">{stats.connections.total}</p>
              </div>
            </Card>
          </div>
        </div>

        {/* Tables */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold">Table Statistics</h3>
          <div className="space-y-2">
            {stats.tables.map((table, idx) => (
              <Card key={idx} className="p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <HardDrive className="h-4 w-4 text-muted-foreground" />
                    <span className="font-semibold font-mono text-sm">{table.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{table.rows.toLocaleString()} rows</Badge>
                    <Badge variant="secondary">{table.size_mb.toFixed(2)} MB</Badge>
                  </div>
                </div>
                <Progress value={(table.rows / totalRows) * 100} />
              </Card>
            ))}
          </div>
        </div>

        {/* Performance Indicators */}
        <div className="p-4 rounded-lg bg-muted space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Query Performance:</span>
            <Badge
              variant={
                stats.avg_query_time_ms < 50
                  ? 'default'
                  : stats.avg_query_time_ms < 100
                  ? 'secondary'
                  : 'destructive'
              }
            >
              {stats.avg_query_time_ms < 50
                ? 'Excellent'
                : stats.avg_query_time_ms < 100
                ? 'Good'
                : 'Needs Optimization'}
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
